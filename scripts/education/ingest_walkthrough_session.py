"""Ingest a RepoCademy session-transcript (JSON v1) — THE education-gate chokepoint.

This is the single, deterministic entry point that converts an *untrusted*
walkthrough/quiz transcript (assembled on the phone, relayed through Supabase, and
handed over by the Phase-2 dev-watcher) into durable capture-stack state:

    transcript.json (untrusted)
        -> full schema validation (pure, zero side effects)
        -> a discussion (Layer 1 dir + Layer 2 `discussions` row)
        -> events.jsonl turns (LOCKED intent map, strictly sequential)
        -> `education_results` rows (one SQLite transaction)
        -> a registry write (re-defer, or the ADDITIVE `clear_eligible` marker),
           written LAST — NEVER a clear

The education gate clears only on the developer's explicit action ("I clear it",
ADR-0035; CONTRACTS.md §1.4 rev 1.1). When the locked formula passes, this ingest
records a durable, additive ``clear_eligible`` marker on the gate (status stays
``open`` — eligible is NOT cleared), reports the gate CLEAR-ELIGIBLE, and prints
the exact ``gate_registry.py clear`` command for the developer (re-printable
later via ``gate_registry.py list --eligible``, so eligibility does not die with
this console). The automatic path never calls ``clear_gate`` — the developer's
CLI clear is the only route to ``status: cleared``. Re-defer (debt bookkeeping,
like ``add``) remains automatic.

Contract: ``docs/education/CONTRACTS.md`` §1 (session-transcript JSON v1). The
phone app builds against that document; the validator here is the STRICT side of
the tolerant-reader/strict-writer split.

Security posture (this file is security-reviewed on every change):
  * The transcript is UNTRUSTED. Nothing is written until the whole payload passes
    validation: required keys, type checks, enum whitelists (imported from
    ``record_education`` — never redefined), ISO-timestamp parseability, the
    ``contract_version == 1`` gate, and the ``^[A-Za-z0-9._-]+$`` charset on
    ``session_id`` / ``gate_id`` (both feed filesystem paths and SQLite keys, so
    this is the path-traversal / injection defense).
  * Scores are CLAMPED to ``[0.0, 1.0]`` (never rejected — LOCKED decision).
  * All SQL is parameterized. Transcript strings are DATA — they are stored as
    event content and never interpolated into SQL, shell, paths, or eval.
  * Validation failure -> exit code 2, one-line stderr message, ZERO writes.

Atomicity, idempotency, and the non-atomic window
--------------------------------------------------
The write sequence is all-or-nothing with best-effort compensation. On any failure
after discussion creation begins, the created discussion directory, its
``discussions`` row, and any ``education_results`` rows for the session are removed;
the registry is left untouched.

Ordering rationale (the one small non-atomic window): the ``education_results``
transaction is COMMITTED **before** the registry is saved. The automatic registry
writes are the re-defer flip and the additive ``clear_eligible`` marker, so a
hard crash in the window leaves the evidence recorded and the gate's label one
step behind it — still ``open`` rather than ``re-deferred``, or eligible-in-fact
but not yet marked. Both fail toward UNDER-claiming: no crash state can make a
gate appear cleared (ADR-0035 removed that direction by construction), and the
marker is a convenience pointer, not the authority — the developer can still
clear directly on the recorded evidence, or re-defer via the CLI. Because the
idempotency guard keys off existing ``education_results`` rows, a naive re-run
of a window-interrupted session is a no-op.

Idempotency: if the gate is already cleared by THIS ``session_id``, any
``education_results`` row already exists for the ``session_id``, or a discussion
with this session's deterministic slug exists (covers zero-education-row sessions,
e.g. an immediate session-level deferral), the run is a no-op (exit 0,
"already ingested"). Re-running never duplicates events or rows and never
overwrites an existing ``cleared_by``.

CLI::

    python scripts/education/ingest_walkthrough_session.py <transcript.json> \
        [--db <path>] [--registry <path>] [--discussions-dir <path>]
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import create_discussion as _cd  # noqa: E402 — sys.path shim must run first
from scripts import write_event as _we  # noqa: E402
from scripts.education import gate_registry as _reg  # noqa: E402
from scripts.record_education import BLOOM_LEVELS, QUESTION_TYPES  # noqa: E402

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
CONTRACT_VERSION = 1
PASS_THRESHOLD = 0.70
ID_RE = _reg.GATE_ID_RE  # ^[A-Za-z0-9._-]+$ — shared with the registry (single source)

# Resource caps on UNTRUSTED input (security finding S1). The transcript arrives
# from outside the trust boundary; without caps a hostile or malfunctioning
# producer could exhaust memory/disk (multi-GB file), flood events.jsonl, or bloat
# education_results. Violations are REJECTED (exit 2, zero writes) — producers
# must stay under these limits (documented in CONTRACTS.md §1.1).
MAX_TRANSCRIPT_BYTES = 2_000_000  # file-size guard, checked BEFORE reading the file
MAX_EVENTS = 500  # a session is minutes-to-hours of narration/quiz, not thousands of turns
MAX_TEXT_LEN = 20_000  # per string field (narration text, answers, rubrics, ...)
MAX_ID_LEN = 128  # session_id / gate_id (both feed paths + DB keys)

MODES = frozenset({"learn", "gate"})
OUTCOME_STATUSES = frozenset({"completed", "session-deferred"})
DEFERRAL_SCOPES = frozenset({"item", "session"})
EVENT_TYPES = frozenset(
    {"narration", "qa_exchange", "quiz_item", "explain_back", "deferral", "completion"}
)
_BLOOM_SET = frozenset(BLOOM_LEVELS)
_QTYPE_SET = frozenset(QUESTION_TYPES)

_TOP_REQUIRED = frozenset(
    {
        "contract_version",
        "session_id",
        "gate_id",
        "repo_slug",
        "mode",
        "started_at",
        "completed_at",
        "events",
        "outcome",
    }
)

# (required_keys, optional_keys) per event type.
_EVENT_KEYS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "narration": (frozenset({"type", "chapter_id", "text"}), frozenset({"chapter_title"})),
    "qa_exchange": (frozenset({"type", "question", "answer"}), frozenset()),
    "quiz_item": (
        frozenset(
            {
                "type",
                "item_id",
                "question",
                "answer",
                "score",
                "bloom",
                "question_type",
                "variant_of",
            }
        ),
        frozenset({"rubric"}),
    ),
    "explain_back": (
        frozenset({"type", "prompt", "answer", "score"}),
        frozenset({"item_id"}),
    ),
    "deferral": (frozenset({"type", "scope", "reason"}), frozenset({"item_ref"})),
    "completion": (frozenset({"type", "summary"}), frozenset()),
}

# LOCKED intent map (docs/education/CONTRACTS.md §1.2). Agents are descriptive
# ("tutor" produced it / "learner" produced it); intents are the fixed 7-value
# write_event enum.
_TUTOR = "tutor"
_LEARNER = "learner"

_EDU_TAGS_BASE = ("education", "repocademy")


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #
class TranscriptValidationError(ValueError):
    """A transcript failed schema validation. Carries a one-line message.

    Raised strictly BEFORE any write. Mapped to CLI exit code 2.
    """


class GateNotFoundError(ValueError):
    """The transcript's ``gate_id`` is not present in the registry.

    A pre-write rejection (zero writes). Mapped to CLI exit code 2.
    """


# --------------------------------------------------------------------------- #
# Result
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class IngestResult:
    """Outcome of an ingest run.

    Attributes:
        gate_id: The gate the transcript targeted.
        outcome: One of ``clear-eligible`` | ``re-deferred`` | ``recorded-open`` |
            ``already-ingested``.
        discussion_id: The created discussion id, or ``None`` for a no-op run.
        event_count: Number of ``events.jsonl`` turns written.
        education_row_count: Number of ``education_results`` rows written.
        changed: ``True`` if the run wrote anything (``False`` for the idempotent
            no-op).
        clear_command: For a ``clear-eligible`` outcome, the exact
            ``gate_registry.py clear`` command for the DEVELOPER to run
            (ADR-0035); ``None`` otherwise. The ingest never runs it.
    """

    gate_id: str
    outcome: str
    discussion_id: str | None
    event_count: int
    education_row_count: int
    changed: bool
    clear_command: str | None = None


@dataclass(frozen=True)
class _Decision:
    """Computed registry action + reported outcome for a validated transcript.

    ``clear`` is deliberately NOT an action any more: the formula passing makes a
    gate CLEAR-ELIGIBLE, and the flip to ``cleared`` is the developer's own CLI
    action (ADR-0035; CONTRACTS.md §1.4 rev 1.1).
    """

    action: str  # "re-defer" | "none"
    outcome: str  # "clear-eligible" | "re-deferred" | "recorded-open"
    reason: str | None  # re-defer reason (session-level deferral reason)


# --------------------------------------------------------------------------- #
# Validation (pure — no side effects)
# --------------------------------------------------------------------------- #
def _is_int(value: Any) -> bool:
    """Return True if ``value`` is a real int (bool is rejected — it subclasses int)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    """Return True if ``value`` is a real int/float (bool rejected)."""
    return isinstance(value, int | float) and not isinstance(value, bool)


def _clamp(score: Any) -> float:
    """Clamp a numeric score into ``[0.0, 1.0]`` (LOCKED: clamp, never reject)."""
    return max(0.0, min(1.0, float(score)))


def _require_str(obj: dict[str, Any], key: str, where: str) -> None:
    """Raise if ``obj[key]`` is not a string or exceeds the per-field length cap."""
    if not isinstance(obj[key], str):
        raise TranscriptValidationError(f"{where}: {key} must be a string")
    if len(obj[key]) > MAX_TEXT_LEN:
        # Deliberately does NOT echo the oversized value.
        raise TranscriptValidationError(
            f"{where}: {key} exceeds the {MAX_TEXT_LEN}-char field cap"
        )


def _require_nonempty_str(obj: dict[str, Any], key: str, where: str) -> None:
    """Raise if ``obj[key]`` is not a non-empty string."""
    _require_str(obj, key, where)
    if not obj[key]:
        raise TranscriptValidationError(f"{where}: {key} must be non-empty")


def _validate_event(event: Any, idx: int) -> None:
    """Validate a single transcript event, raising ``TranscriptValidationError``."""
    where = f"events[{idx}]"
    if not isinstance(event, dict):
        raise TranscriptValidationError(f"{where} must be an object")
    etype = event.get("type")
    if etype not in EVENT_TYPES:
        raise TranscriptValidationError(f"{where}: unknown event type {etype!r}")

    required, optional = _EVENT_KEYS[etype]
    keys = set(event)
    missing = required - keys
    if missing:
        raise TranscriptValidationError(f"{where} ({etype}) missing keys: {sorted(missing)}")
    unknown = keys - required - optional
    if unknown:
        raise TranscriptValidationError(f"{where} ({etype}) has unknown keys: {sorted(unknown)}")

    if etype == "narration":
        _require_str(event, "chapter_id", where)
        _require_str(event, "text", where)
        if "chapter_title" in event:
            _require_str(event, "chapter_title", where)
    elif etype == "qa_exchange":
        _require_str(event, "question", where)
        _require_str(event, "answer", where)
    elif etype == "quiz_item":
        _require_str(event, "item_id", where)
        _require_str(event, "question", where)
        _require_str(event, "answer", where)
        if not _is_number(event["score"]):
            raise TranscriptValidationError(f"{where}: score must be a number")
        if event["bloom"] not in _BLOOM_SET:
            raise TranscriptValidationError(
                f"{where}: bloom {event['bloom']!r} must be one of {sorted(_BLOOM_SET)}"
            )
        if event["question_type"] not in _QTYPE_SET:
            raise TranscriptValidationError(
                f"{where}: question_type {event['question_type']!r} must be one of "
                f"{sorted(_QTYPE_SET)}"
            )
        variant_of = event["variant_of"]
        if variant_of is not None and not isinstance(variant_of, str):
            raise TranscriptValidationError(f"{where}: variant_of must be a string or null")
        if "rubric" in event:
            _require_str(event, "rubric", where)
    elif etype == "explain_back":
        _require_str(event, "prompt", where)
        _require_str(event, "answer", where)
        if not _is_number(event["score"]):
            raise TranscriptValidationError(f"{where}: score must be a number")
        if "item_id" in event:
            _require_str(event, "item_id", where)
    elif etype == "deferral":
        if event["scope"] not in DEFERRAL_SCOPES:
            raise TranscriptValidationError(
                f"{where}: scope {event['scope']!r} must be one of {sorted(DEFERRAL_SCOPES)}"
            )
        _require_str(event, "reason", where)
        if "item_ref" in event:
            _require_str(event, "item_ref", where)
    elif etype == "completion":
        _require_str(event, "summary", where)


def _validate_outcome(outcome: Any, events: list[dict[str, Any]]) -> None:
    """Validate the outcome block and its consistency with session-level deferral."""
    if not isinstance(outcome, dict):
        raise TranscriptValidationError("outcome must be an object")
    keys = set(outcome)
    if "status" not in keys:
        raise TranscriptValidationError("outcome missing required key: status")
    unknown = keys - {"status", "summary"}
    if unknown:
        raise TranscriptValidationError(f"outcome has unknown keys: {sorted(unknown)}")
    status = outcome["status"]
    if status not in OUTCOME_STATUSES:
        raise TranscriptValidationError(
            f"outcome.status {status!r} must be one of {sorted(OUTCOME_STATUSES)}"
        )
    if "summary" in outcome:
        _require_str(outcome, "summary", "outcome")

    session_defs = [e for e in events if e["type"] == "deferral" and e["scope"] == "session"]
    if len(session_defs) > 1:
        raise TranscriptValidationError("at most one session-level deferral is allowed")
    has_session_def = len(session_defs) == 1
    if has_session_def and status != "session-deferred":
        raise TranscriptValidationError(
            "outcome.status must be 'session-deferred' when a session-level deferral event exists"
        )
    if not has_session_def and status == "session-deferred":
        raise TranscriptValidationError(
            "outcome.status is 'session-deferred' but no session-level deferral event exists"
        )


def validate_transcript(data: Any) -> dict[str, Any]:
    """Validate a session-transcript against CONTRACTS.md v1, raising on any defect.

    This is a PURE function: it never writes. Callers rely on that — a raised
    ``TranscriptValidationError`` guarantees zero side effects.

    Args:
        data: The parsed transcript object (typically from ``json.load``).

    Returns:
        The same mapping, once fully validated.

    Raises:
        TranscriptValidationError: On a non-object root, a missing/unknown key, a
            bad enum, a bad ID charset, a wrong ``contract_version``, an
            unparseable timestamp, or any per-event / outcome defect.
    """
    if not isinstance(data, dict):
        raise TranscriptValidationError(
            f"transcript root must be an object, got {type(data).__name__}"
        )
    keys = set(data)
    missing = _TOP_REQUIRED - keys
    if missing:
        raise TranscriptValidationError(f"transcript missing required keys: {sorted(missing)}")
    unknown = keys - _TOP_REQUIRED
    if unknown:
        raise TranscriptValidationError(f"transcript has unknown keys: {sorted(unknown)}")

    cv = data["contract_version"]
    if not _is_int(cv) or cv != CONTRACT_VERSION:
        raise TranscriptValidationError(
            f"contract_version must be the int {CONTRACT_VERSION}, got {cv!r}"
        )

    for id_key in ("session_id", "gate_id"):
        value = data[id_key]
        if not isinstance(value, str) or not ID_RE.match(value):
            raise TranscriptValidationError(
                f"{id_key} {value!r} must be a string matching ^[A-Za-z0-9._-]+$"
            )
        if len(value) > MAX_ID_LEN:
            raise TranscriptValidationError(f"{id_key} exceeds the {MAX_ID_LEN}-char cap")

    repo_slug = data["repo_slug"]
    if not isinstance(repo_slug, str) or not (1 <= len(repo_slug) <= 200):
        raise TranscriptValidationError("repo_slug must be a non-empty string (<= 200 chars)")

    if data["mode"] not in MODES:
        raise TranscriptValidationError(f"mode {data['mode']!r} must be one of {sorted(MODES)}")

    for ts_key in ("started_at", "completed_at"):
        value = data[ts_key]
        if not isinstance(value, str):
            raise TranscriptValidationError(f"{ts_key} must be an ISO-8601 string")
        try:
            datetime.fromisoformat(value)
        except ValueError as exc:
            raise TranscriptValidationError(
                f"{ts_key} is not a parseable ISO-8601 timestamp: {value!r}"
            ) from exc

    events = data["events"]
    if not isinstance(events, list):
        raise TranscriptValidationError("events must be a list")
    if len(events) > MAX_EVENTS:
        raise TranscriptValidationError(
            f"events count {len(events)} exceeds the {MAX_EVENTS}-event cap"
        )
    for idx, event in enumerate(events):
        _validate_event(event, idx)

    _validate_outcome(data["outcome"], events)
    return data


# --------------------------------------------------------------------------- #
# Derivations from a validated transcript (pure)
# --------------------------------------------------------------------------- #
def _event_turns(transcript: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Map validated events onto ordered ``(agent, intent, content)`` turns.

    Intent mapping is LOCKED (CONTRACTS.md §1.2). Content strings are derived DATA
    — never interpolated into SQL/paths/eval.
    """
    turns: list[tuple[str, str, str]] = []
    for event in transcript["events"]:
        etype = event["type"]
        if etype == "narration":
            turns.append((_TUTOR, "proposal", event["text"]))
        elif etype == "qa_exchange":
            turns.append((_LEARNER, "question", event["question"]))
            turns.append((_TUTOR, "evidence", event["answer"]))
        elif etype == "quiz_item":
            turns.append((_TUTOR, "question", event["question"]))
            turns.append((_LEARNER, "evidence", event["answer"]))
            turns.append((_TUTOR, "critique", _grade_text(event["score"], event.get("rubric"))))
        elif etype == "explain_back":
            turns.append((_TUTOR, "question", event["prompt"]))
            turns.append((_LEARNER, "evidence", event["answer"]))
            turns.append((_TUTOR, "critique", _grade_text(event["score"], None)))
        elif etype == "deferral":
            ref = f" [item_ref: {event['item_ref']}]" if event.get("item_ref") else ""
            turns.append(
                (_LEARNER, "decision", f"deferral ({event['scope']}): {event['reason']}{ref}")
            )
        elif etype == "completion":
            turns.append((_TUTOR, "synthesis", event["summary"]))
    return turns


def _grade_text(score: Any, rubric: str | None) -> str:
    """Build the ``critique`` content for a graded item (clamped score + pass flag)."""
    clamped = _clamp(score)
    text = f"graded: score={clamped:.2f} passed={clamped >= PASS_THRESHOLD}"
    if rubric:
        text += f" | rubric: {rubric}"
    return text


def _education_rows(transcript: dict[str, Any]) -> list[tuple[str, str, float, bool]]:
    """Map validated events onto ordered ``education_results`` rows.

    Returns ``(bloom_level, question_type, score, passed)`` tuples. narration ->
    understand/walkthrough/1.0/passed; quiz_item -> item bloom/type/clamped-score/
    (score>=0.70); explain_back -> evaluate/explain-back/clamped-score/(score>=0.70).
    """
    rows: list[tuple[str, str, float, bool]] = []
    for event in transcript["events"]:
        etype = event["type"]
        if etype == "narration":
            rows.append(("understand", "walkthrough", 1.0, True))
        elif etype == "quiz_item":
            score = _clamp(event["score"])
            rows.append((event["bloom"], event["question_type"], score, score >= PASS_THRESHOLD))
        elif etype == "explain_back":
            score = _clamp(event["score"])
            rows.append(("evaluate", "explain-back", score, score >= PASS_THRESHOLD))
    return rows


def _decide(transcript: dict[str, Any]) -> _Decision:
    """Compute the authoritative verdict from validated events (LOCKED rule).

    clear-eligible  <=>  walked AND terminal-quiz-avg >= 0.70 AND explain-back
    passed. Eligibility is NOT clearance: the flip to ``cleared`` is the
    developer's own ``gate_registry.py clear`` (ADR-0035), so the eligible branch
    carries registry action "none". A session-level deferral re-defers instead.
    ``mode == "gate"`` is a PRECONDITION for ANY registry action *and* for
    eligibility itself: learn-mode sessions never touch the registry, even when
    they contain a session-level deferral (ADR-0029; arch finding A2). See
    CONTRACTS.md §1.4 (rev 1.1).
    """
    events = transcript["events"]

    if transcript["mode"] != "gate":
        # Learn-mode: record evidence only; the registry is NEVER touched —
        # this check deliberately precedes the session-deferral check.
        return _Decision(action="none", outcome="recorded-open", reason=None)

    session_reason = next(
        (e["reason"] for e in events if e["type"] == "deferral" and e["scope"] == "session"),
        None,
    )
    if session_reason is not None:
        return _Decision(action="re-defer", outcome="re-deferred", reason=session_reason)

    walked = any(e["type"] == "narration" for e in events)

    quiz_items = [e for e in events if e["type"] == "quiz_item"]
    superseded = {e["variant_of"] for e in quiz_items if e.get("variant_of")}
    terminal_scores = [_clamp(e["score"]) for e in quiz_items if e["item_id"] not in superseded]
    quiz_passed = bool(terminal_scores) and (
        sum(terminal_scores) / len(terminal_scores) >= PASS_THRESHOLD
    )

    explain_scores = [_clamp(e["score"]) for e in events if e["type"] == "explain_back"]
    explain_passed = bool(explain_scores) and all(s >= PASS_THRESHOLD for s in explain_scores)

    if walked and quiz_passed and explain_passed:
        return _Decision(action="none", outcome="clear-eligible", reason=None)
    return _Decision(action="none", outcome="recorded-open", reason=None)


# --------------------------------------------------------------------------- #
# Idempotency + compensation (side-effecting helpers)
# --------------------------------------------------------------------------- #
def _session_slug(gate_id: str, session_id: str) -> str:
    """Deterministic discussion slug for a (gate, session) pair.

    Embedding the lowercased ``session_id`` makes every prior ingest of a session
    detectable via the ``discussions`` table — including sessions that produced
    ZERO ``education_results`` rows (e.g. a session-level deferral before any
    narration/quiz), which would otherwise escape the row-based guard (arch
    finding A4). Both IDs are pre-validated to ``^[A-Za-z0-9._-]+$``, so the slug
    is path- and ID-safe.
    """
    return f"education-{gate_id.lower()}-{session_id.lower()}"


def _already_ingested(
    registry: dict[str, Any], gate_id: str, session_id: str, db_path: Path
) -> bool:
    """Return True if this session was already ingested (no-op guard).

    True when ANY prior ingest of the ``session_id`` is detectable:
    the gate is already cleared by THIS ``session_id``, an ``education_results``
    row exists for it, or a discussion with this session's deterministic slug
    exists (covers zero-education-row sessions such as an immediate
    session-level deferral).
    """
    gate = _reg.get_gate(registry, gate_id)
    cleared_by = gate.get("cleared_by")
    if (
        gate.get("status") == "cleared"
        and isinstance(cleared_by, dict)
        and cleared_by.get("session_id") == session_id
    ):
        return True
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT 1 FROM education_results WHERE session_id = ? LIMIT 1",
            (session_id,),
        ).fetchone()
        if row is None:
            # Discussion IDs are DISC-YYYYMMDD-HHMMSS-<slug>: a fixed 21-char
            # prefix, so an exact substr match on the deterministic slug is
            # unambiguous (no LIKE wildcard/suffix pitfalls).
            row = conn.execute(
                "SELECT 1 FROM discussions WHERE substr(discussion_id, 22) = ? LIMIT 1",
                (_session_slug(gate_id, session_id),),
            ).fetchone()
    finally:
        conn.close()
    return row is not None


def _compensate(discussion_id: str | None, session_id: str, db_path: Path) -> None:
    """Best-effort rollback: remove the discussion (dir + row) and this session's rows.

    Safe to call whether or not the education transaction committed — ``DELETE`` is
    used, so committed rows are removed and uncommitted rows are a no-op.
    """
    if discussion_id is None:
        return
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute(
                "DELETE FROM education_results WHERE session_id = ? AND discussion_id = ?",
                (session_id, discussion_id),
            )
            conn.execute("DELETE FROM discussions WHERE discussion_id = ?", (discussion_id,))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        # Compensation failure recreates the orphaned-evidence state — it must be
        # observable, never silent (finding IP6). Best-effort continues regardless.
        print(
            f"warning: compensation failed for discussion {discussion_id} "
            f"(session_id={session_id}): {exc}",
            file=sys.stderr,
        )
    try:
        disc_dir = _we.find_discussion_dir(discussion_id)
        shutil.rmtree(disc_dir, ignore_errors=True)
    except FileNotFoundError:
        pass


# --------------------------------------------------------------------------- #
# Core ingest
# --------------------------------------------------------------------------- #
def ingest_transcript(
    transcript: dict[str, Any],
    *,
    db_path: Path,
    registry_path: Path,
    discussions_dir: Path,
) -> IngestResult:
    """Validate then ingest a transcript into the capture stack (all-or-nothing).

    Args:
        transcript: A parsed transcript object (validated defensively here).
        db_path: SQLite ``evaluation.db`` to write discussion + education rows into.
        registry_path: ``gates.yaml`` to flip.
        discussions_dir: Root ``discussions/`` directory for the Layer 1 dir.

    Returns:
        An :class:`IngestResult` describing the outcome.

    Raises:
        TranscriptValidationError: Invalid transcript (pre-write; zero writes).
        GateNotFoundError: ``gate_id`` not in the registry (pre-write; zero writes).
        Exception: Any post-write failure, AFTER best-effort compensation has run
            (discussion + rows removed, registry untouched).
    """
    db_path = Path(db_path)
    registry_path = Path(registry_path)
    discussions_dir = Path(discussions_dir)

    transcript = validate_transcript(transcript)
    gate_id = transcript["gate_id"]
    session_id = transcript["session_id"]

    registry = _reg.load_registry(registry_path)
    try:
        _reg.get_gate(registry, gate_id)
    except KeyError as exc:
        raise GateNotFoundError(
            f"gate {gate_id!r} not present in registry {registry_path}"
        ) from exc

    if _already_ingested(registry, gate_id, session_id, db_path):
        return IngestResult(
            gate_id=gate_id,
            outcome="already-ingested",
            discussion_id=None,
            event_count=0,
            education_row_count=0,
            changed=False,
        )

    decision = _decide(transcript)
    turns = _event_turns(transcript)
    rows = _education_rows(transcript)
    tags = [*_EDU_TAGS_BASE, f"gate:{gate_id}"]

    # The reused create_discussion / write_event helpers key off module globals for
    # their target paths. Point them at our targets, and RESTORE afterwards so a
    # library call never leaks global state into the rest of the process.
    # NOTE: this mutation is NOT thread-safe — it is sound only under the
    # documented single-writer topology (one sequential ingest/watcher process;
    # CONTRACTS.md §4, ADR-0029). Revisit if the ingest is ever parallelized.
    _orig = (_cd.DB_PATH, _cd.DISCUSSIONS_DIR, _we.DISCUSSIONS_DIR)
    _cd.DB_PATH = db_path
    _cd.DISCUSSIONS_DIR = discussions_dir
    _we.DISCUSSIONS_DIR = discussions_dir

    discussion_id: str | None = None
    try:
        # Step 2 — discussion (Layer 1 dir + Layer 2 row). The slug embeds the
        # session_id so the idempotency guard can detect zero-education-row
        # sessions (see _session_slug). create_discussion prints its id to
        # stdout; that print is suppressed here so the watcher sees ONLY the
        # ingest's own summary line (security finding S3).
        with contextlib.redirect_stdout(io.StringIO()):
            discussion_id = _cd.create_discussion(
                slug=_session_slug(gate_id, session_id),
                risk_level="low",
                collaboration_mode="ensemble",
                exploration_intensity="low",
                command_type="education",
            )

        # Step 3 — events.jsonl turns, strictly sequential (NEVER parallel).
        for agent, intent, content in turns:
            _we.write_event(discussion_id, agent, intent, content, tags=tags)

        # Step 4 — education_results rows in ONE transaction.
        stamped = datetime.now(UTC).isoformat()
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.executemany(
                "INSERT INTO education_results "
                "(session_id, discussion_id, bloom_level, question_type, "
                "score, passed, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (session_id, discussion_id, bloom, qtype, score, passed, stamped)
                    for (bloom, qtype, score, passed) in rows
                ],
            )
            conn.commit()
        finally:
            conn.close()

        # Step 5 — registry write LAST (see module docstring: non-atomic window).
        # The automatic path never calls clear_gate: "cleared" is reachable ONLY
        # through the developer's own gate_registry.py clear (ADR-0035). The two
        # automatic writes are the re-defer bookkeeping and the ADDITIVE
        # clear_eligible marker — status stays open; eligible is not cleared.
        if decision.action == "re-defer":
            _reg.re_defer_gate(registry, gate_id, decision.reason or "session-level deferral")
            _reg.save_registry(registry, registry_path)
        elif decision.outcome == "clear-eligible":
            _reg.mark_clear_eligible(registry, gate_id, session_id, discussion_id)
            _reg.save_registry(registry, registry_path)
        # otherwise: registry deliberately untouched.
    except BaseException:
        _compensate(discussion_id, session_id, db_path)
        raise
    finally:
        _cd.DB_PATH, _cd.DISCUSSIONS_DIR, _we.DISCUSSIONS_DIR = _orig

    clear_command: str | None = None
    if decision.outcome == "clear-eligible":
        # Paste-ready for the DEVELOPER, rebuilt from the durable marker (and
        # re-printable later via `gate_registry.py list --eligible`). Both ids are
        # pre-validated to ^[A-Za-z0-9._-]+$, so interpolation cannot smuggle
        # flags; clear_command_for adds --registry when this run's registry is not
        # the default, so the paste never mutates the wrong file.
        clear_command = _reg.clear_command_for(_reg.get_gate(registry, gate_id), registry_path)

    return IngestResult(
        gate_id=gate_id,
        outcome=decision.outcome,
        discussion_id=discussion_id,
        event_count=len(turns),
        education_row_count=len(rows),
        changed=True,
        clear_command=clear_command,
    )


def load_transcript(path: Path) -> dict[str, Any]:
    """Read + parse + validate a transcript file.

    Args:
        path: Path to the transcript JSON file.

    Returns:
        The validated transcript mapping.

    Raises:
        TranscriptValidationError: On unreadable file, invalid JSON, or schema
            violation (all pre-write; unified so the CLI maps them to exit 2).
    """
    try:
        size = Path(path).stat().st_size
    except OSError as exc:
        raise TranscriptValidationError(f"cannot read transcript {path}: {exc}") from exc
    if size > MAX_TRANSCRIPT_BYTES:
        # Size guard runs BEFORE read_text so an oversized file is never loaded.
        raise TranscriptValidationError(
            f"transcript file is {size} bytes; cap is {MAX_TRANSCRIPT_BYTES} (S1 resource cap)"
        )
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise TranscriptValidationError(f"cannot read transcript {path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TranscriptValidationError(f"transcript is not valid JSON: {path}: {exc}") from exc
    return validate_transcript(data)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for the CLI."""
    parser = argparse.ArgumentParser(
        description="Ingest a RepoCademy session-transcript (JSON v1) into the capture stack."
    )
    parser.add_argument("transcript", help="Path to the transcript JSON file")
    parser.add_argument(
        "--db",
        default=str(PROJECT_ROOT / "metrics" / "evaluation.db"),
        help="SQLite evaluation.db path (default: metrics/evaluation.db)",
    )
    parser.add_argument(
        "--registry",
        default=str(_reg.DEFAULT_REGISTRY_PATH),
        help="gates.yaml registry path (default: docs/education/gates.yaml)",
    )
    parser.add_argument(
        "--discussions-dir",
        default=str(PROJECT_ROOT / "discussions"),
        help="Root discussions/ directory (default: discussions/)",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Argument vector (defaults to ``sys.argv[1:]``).

    Returns:
        Exit code: 0 on success or idempotent no-op; 2 on validation / gate-not-found
        rejection (zero writes); 1 on a post-write failure (compensated).
    """
    args = build_parser().parse_args(argv)
    try:
        transcript = load_transcript(Path(args.transcript))
        result = ingest_transcript(
            transcript,
            db_path=Path(args.db),
            registry_path=Path(args.registry),
            discussions_dir=Path(args.discussions_dir),
        )
    except (TranscriptValidationError, GateNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # post-write failure; compensation already ran
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not result.changed:
        # Explicit + includes session_id so cross-device session_id collisions are
        # observable in watcher logs, never silent (finding IP4). Both guard paths
        # (cleared-by-session, prior-evidence/discussion) funnel through here.
        print(
            f"Gate {result.gate_id}: already ingested - no-op "
            f"(session_id={transcript['session_id']})"
        )
        return 0
    print(
        f"Ingested gate {result.gate_id}: outcome={result.outcome}, "
        f"events={result.event_count}, education_rows={result.education_row_count}, "
        f"discussion={result.discussion_id}"
    )
    if result.clear_command:
        # The gate is CLEAR-ELIGIBLE, not cleared: the registry gained only the
        # additive marker; clearing is the developer's explicit action (ADR-0035;
        # CONTRACTS.md §1.4 rev 1.1). Print the evidence pointer and the
        # paste-ready command (re-printable via `gate_registry.py list --eligible`).
        print(
            f"Gate {result.gate_id} is CLEAR-ELIGIBLE "
            f"(walked AND quiz_avg >= {PASS_THRESHOLD} AND explain_back passed); "
            f"evidence: discussion={result.discussion_id}."
        )
        print(
            "Marked clear-eligible in the registry (status stays open; eligible is "
            "not cleared). Developer: to clear this gate, run:"
        )
        print(f"  {result.clear_command}")
    return 0


def main() -> None:
    """Module entry point."""
    raise SystemExit(run())


if __name__ == "__main__":
    main()
