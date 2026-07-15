"""Ingest a RepoCademy walkthrough-session transcript into the capture pipeline.

THE education-gate chokepoint (ADR-0029): any client that emits a valid
session-transcript JSON (contract v1 — see docs/education/CONTRACTS.md) clears
gates through the exact same machinery as /quiz: a Layer-1 discussion,
events.jsonl, education_results rows, and a gates.yaml flip.

Transcripts are UNTRUSTED input (they arrive from a phone via Supabase or from
any file handed to this script): everything is validated before anything is
written, enums are whitelisted against record_education.py's CHECK constraints,
scores must be in [0, 1], the client-supplied pass_threshold is floored at 0.5,
free text is stripped of control characters / ANSI sequences, and transcript
content is never interpolated into shell commands or SQL (library calls +
parameterized SQL only).

TRUST MODEL (load-bearing): quiz and explain-back GRADES are client-asserted —
the client's LLM graded the developer's spoken answers. This script therefore
performs REGISTRATION, not certification. The certification step for a gate is
the human developer reviewing and merging the evidence PR that carries this
transcript (or, when running locally, the developer choosing to run this
script). A registry flip produced by ingest is evidence-backed and auditable
(full transcript in the sealed discussion), never self-certifying.

Write discipline: validate-then-write. Writes are sequential — events.jsonl
lines, then all education_results rows in ONE SQLite transaction, then the
registry flip — and idempotency is keyed on session_id in education_results.
If a crash lands between the DB transaction and the registry save, re-runs
report "already ingested"; recover by flipping the gate manually:
`python scripts/education/gate_registry.py clear <GATE-ID> --session <VWALK-ID>`.

Usage:
    python scripts/education/ingest_walkthrough_session.py <transcript.json> [--no-close]
"""

import argparse
import json
import re
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts import create_discussion as create_discussion_module
from scripts import write_event as write_event_module
from scripts.education import gate_registry

PROJECT_ROOT = Path(__file__).parent.parent.parent
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"

CONTRACT_VERSION = 1
SESSION_ID_RE = re.compile(r"^VWALK-\d{8}-\d{6}$")
VALID_CLIENTS = {"phone", "tablet", "laptop", "chat"}
VALID_MODES = {"learn", "gate"}
VALID_BLOOM = {"remember", "understand", "apply", "analyze", "evaluate", "create"}
VALID_QUESTION_TYPES = {"recall", "walkthrough", "debug-scenario", "change-impact", "explain-back"}
VALID_EVENT_TYPES = {
    "narration",
    "question",
    "answer",
    "parked_question",
    "quiz_question",
    "quiz_answer",
    "quiz_grade",
    "explain_back_prompt",
    "explain_back_answer",
    "explain_back_grade",
    "deferral",
}
MAX_TEXT_LEN = 50_000
MAX_EVENTS = 2_000
MAX_TOTAL_TEXT = 2_000_000  # cap on summed free-text bytes per transcript (DoS guard)
DEFAULT_PASS_THRESHOLD = 0.70
MIN_PASS_THRESHOLD = 0.5  # the bar is not client-nullable (review finding)

# Control characters (except \n and \t) and ANSI CSI/OSC escape sequences: stripped
# from every free-text field before it reaches events.jsonl / gates.yaml / a terminal
# (security review REV-20260715: terminal-injection via crafted transcripts).
_CONTROL_CHARS_RE = re.compile(
    # Order matters: full ANSI CSI/OSC sequences first (so ESC consumes its whole
    # sequence), then the bare control-character fallback (which includes ESC).
    r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07]*(?:\x07|\x1b\\)?|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"
)


class TranscriptError(ValueError):
    """Raised when a transcript fails validation. Nothing has been written."""


def seal_discussion(discussion_id: str) -> None:
    """Seal the discussion via close_discussion (lazy import — it uses flat
    sibling imports and cannot be imported as a package module at load time)."""
    scripts_dir = str(Path(__file__).parent.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from close_discussion import close_discussion

    close_discussion(discussion_id)


def _slugify(value: str, max_len: int = 40) -> str:
    """Reduce untrusted text to a safe discussion-slug fragment."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:max_len] or "chapter"


def _sanitize_text(value: str) -> str:
    """Strip control characters and ANSI escape sequences from untrusted text."""
    return _CONTROL_CHARS_RE.sub("", value)


def sanitize_transcript(transcript: dict[str, Any]) -> None:
    """Sanitize every free-text field in place (call after validation).

    Covers event text/feedback/section, the chapter title, and course_id —
    everything that later lands in events.jsonl, gates.yaml, or CLI output.

    Args:
        transcript: A transcript that has already passed validate_transcript.
    """
    chapter = transcript["chapter"]
    chapter["title"] = _sanitize_text(chapter["title"])
    if isinstance(transcript.get("course_id"), str):
        transcript["course_id"] = _sanitize_text(transcript["course_id"])
    for event in transcript["events"]:
        for field in ("text", "feedback", "section"):
            if isinstance(event.get(field), str):
                event[field] = _sanitize_text(event[field])


def _require_text(errors: list[str], event: dict[str, Any], index: int) -> None:
    text = event.get("text")
    if not isinstance(text, str) or not text.strip():
        errors.append(f"events[{index}]: 'text' must be a non-empty string")
    elif len(text) > MAX_TEXT_LEN:
        errors.append(f"events[{index}]: 'text' exceeds {MAX_TEXT_LEN} chars")


def _require_score(errors: list[str], event: dict[str, Any], index: int) -> None:
    score = event.get("score")
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        errors.append(f"events[{index}]: 'score' must be a number")
    elif not 0.0 <= float(score) <= 1.0:
        errors.append(f"events[{index}]: 'score' must be within [0, 1]")


def validate_transcript(data: Any) -> dict[str, Any]:
    """Validate an untrusted transcript; raise TranscriptError listing every defect.

    Args:
        data: Parsed JSON payload.

    Returns:
        The validated transcript mapping (same object).
    """
    errors: list[str] = []
    if not isinstance(data, dict):
        raise TranscriptError("Transcript root must be a JSON object")

    if data.get("contract_version") != CONTRACT_VERSION:
        errors.append(f"contract_version must be {CONTRACT_VERSION}")
    session_id = data.get("session_id", "")
    if not isinstance(session_id, str) or not SESSION_ID_RE.match(session_id):
        errors.append("session_id must match VWALK-YYYYMMDD-HHMMSS")
    if data.get("client") not in VALID_CLIENTS:
        errors.append(f"client must be one of {sorted(VALID_CLIENTS)}")
    mode = data.get("mode")
    if mode not in VALID_MODES:
        errors.append(f"mode must be one of {sorted(VALID_MODES)}")
    if mode == "gate":
        gate_id = data.get("gate_id", "")
        if not isinstance(gate_id, str) or not gate_registry.GATE_ID_RE.match(gate_id):
            errors.append("gate mode requires a valid gate_id (GATE-NNNN)")
    chapter = data.get("chapter")
    if not isinstance(chapter, dict) or not isinstance(chapter.get("title"), str):
        errors.append("chapter must be an object with a string 'title'")
    elif "number" in chapter and (
        not isinstance(chapter["number"], int) or isinstance(chapter["number"], bool)
    ):
        errors.append("chapter.number must be an integer when present")
    if data.get("narration_completed") is not True:
        errors.append("narration_completed must be true (only completed sessions are ingested)")

    events = data.get("events")
    if not isinstance(events, list) or not events:
        errors.append("events must be a non-empty list")
        events = []
    if len(events) > MAX_EVENTS:
        errors.append(f"events exceeds the {MAX_EVENTS}-event cap")
        events = []

    quiz_questions: dict[str, dict[str, Any]] = {}
    for i, event in enumerate(events):
        if not isinstance(event, dict):
            errors.append(f"events[{i}]: must be an object")
            continue
        etype = event.get("type")
        if etype not in VALID_EVENT_TYPES:
            errors.append(f"events[{i}]: unknown type {etype!r}")
            continue
        if etype in ("quiz_grade", "explain_back_grade"):
            _require_score(errors, event, i)
        else:
            _require_text(errors, event, i)
        if etype == "quiz_question":
            qid = event.get("qid")
            if not isinstance(qid, str) or not qid:
                errors.append(f"events[{i}]: quiz_question requires a 'qid'")
            elif qid in quiz_questions:
                errors.append(f"events[{i}]: duplicate qid {qid!r}")
            else:
                quiz_questions[qid] = event
            if event.get("bloom_level") not in VALID_BLOOM:
                errors.append(f"events[{i}]: bloom_level must be one of {sorted(VALID_BLOOM)}")
            if event.get("question_type") not in VALID_QUESTION_TYPES:
                errors.append(
                    f"events[{i}]: question_type must be one of {sorted(VALID_QUESTION_TYPES)}"
                )
        if etype in ("quiz_answer", "quiz_grade"):
            qid = event.get("qid")
            if not isinstance(qid, str) or qid not in quiz_questions:
                errors.append(f"events[{i}]: {etype} references unknown qid {event.get('qid')!r}")

    total_text = sum(
        len(e.get("text", ""))
        for e in events
        if isinstance(e, dict) and isinstance(e.get("text"), str)
    )
    if total_text > MAX_TOTAL_TEXT:
        errors.append(f"total transcript text exceeds the {MAX_TOTAL_TEXT}-char cap")

    quiz_summary = data.get("quiz_summary", {})
    if quiz_summary is not None and not isinstance(quiz_summary, dict):
        errors.append("quiz_summary must be an object when present")
    else:
        threshold = (quiz_summary or {}).get("pass_threshold", DEFAULT_PASS_THRESHOLD)
        if (
            not isinstance(threshold, (int, float))
            or isinstance(threshold, bool)
            or not MIN_PASS_THRESHOLD <= float(threshold) <= 1.0
        ):
            errors.append(
                f"quiz_summary.pass_threshold must be a number in [{MIN_PASS_THRESHOLD}, 1]"
            )
        claimed_average = (quiz_summary or {}).get("average")
        if claimed_average is not None:
            grades = [
                float(e["score"])
                for e in events
                if isinstance(e, dict)
                and e.get("type") == "quiz_grade"
                and isinstance(e.get("score"), (int, float))
                and not isinstance(e.get("score"), bool)
            ]
            if not isinstance(claimed_average, (int, float)) or isinstance(claimed_average, bool):
                errors.append("quiz_summary.average must be a number when present")
            elif grades and abs(sum(grades) / len(grades) - float(claimed_average)) > 0.01:
                errors.append("quiz_summary.average is inconsistent with the quiz_grade events")

    if errors:
        raise TranscriptError("Invalid transcript:\n  - " + "\n  - ".join(errors))
    return data


def already_ingested(session_id: str, db_path: Path = DB_PATH) -> bool:
    """Return True if any education_results row exists for this session.

    Args:
        session_id: The VWALK session id.
        db_path: SQLite database path.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT 1 FROM education_results WHERE session_id = ? LIMIT 1", (session_id,)
        ).fetchone()
    finally:
        conn.close()
    return row is not None


def _gate_outcome(transcript: dict[str, Any]) -> tuple[float | None, bool]:
    """Compute (quiz_average, gate_cleared) per the R5 gate-cleared rule."""
    threshold = float(
        (transcript.get("quiz_summary") or {}).get("pass_threshold", DEFAULT_PASS_THRESHOLD)
    )
    grades = [float(e["score"]) for e in transcript["events"] if e["type"] == "quiz_grade"]
    explain_scores = [
        float(e["score"]) for e in transcript["events"] if e["type"] == "explain_back_grade"
    ]
    deferred = any(e["type"] == "deferral" for e in transcript["events"])
    quiz_average = sum(grades) / len(grades) if grades else None
    cleared = (
        not deferred
        and quiz_average is not None
        and quiz_average >= threshold
        and bool(explain_scores)
        and all(s >= threshold for s in explain_scores)
    )
    return quiz_average, cleared


def ingest(
    transcript: dict[str, Any],
    db_path: Path = DB_PATH,
    registry_path: Path = gate_registry.REGISTRY_PATH,
    close: bool = True,
) -> dict[str, Any]:
    """Ingest a validated transcript: discussion + events + education rows + registry.

    Validate-then-write: all validation (transcript schema, idempotency, gate
    existence) happens before the first write. Re-running the same session is a
    no-op.

    Args:
        transcript: Parsed transcript JSON (validated here).
        db_path: evaluation.db path.
        registry_path: gates.yaml path.
        close: Whether to seal the discussion via close_discussion (best-effort).

    Returns:
        Summary mapping: discussion_id, rows_recorded, gate_id, gate_cleared,
        quiz_average, parked_questions, skipped.
    """
    validate_transcript(transcript)
    sanitize_transcript(transcript)
    session_id = transcript["session_id"]

    if already_ingested(session_id, db_path):
        return {"skipped": True, "reason": f"session {session_id} already ingested"}

    mode = transcript["mode"]
    gate_id = transcript.get("gate_id")
    registry = None
    if mode == "gate":
        registry = gate_registry.load_registry(registry_path)
        gate = gate_registry.get_gate(registry, gate_id)
        if gate["status"] == "cleared":
            return {"skipped": True, "reason": f"{gate_id} is already cleared"}

    chapter = transcript["chapter"]
    threshold = float(
        (transcript.get("quiz_summary") or {}).get("pass_threshold", DEFAULT_PASS_THRESHOLD)
    )
    quiz_average, cleared = _gate_outcome(transcript)
    chapter_tag = f"chapter-{int(chapter.get('number', 0)):02d}"
    course_tag = f"course:{_slugify(str(transcript.get('course_id', 'adhoc')))}"

    slug = f"walkthrough-{mode}-{_slugify(chapter['title'])}"
    discussion_id = create_discussion_module.create_discussion(
        slug, risk_level="low", collaboration_mode="ensemble"
    )

    def emit(
        agent: str, intent: str, content: str, tags: list[str], reply_to: int | None = None
    ) -> int:
        return write_event_module.write_event(
            discussion_id, agent, intent, content, reply_to=reply_to, tags=tags
        )

    base_tags = ["education", "voice", course_tag, chapter_tag]
    education_rows: list[tuple[str, str, float, bool]] = []  # (bloom, qtype, score, passed)
    parked: list[str] = []
    last_question_turn: int | None = None
    quiz_meta: dict[str, dict[str, Any]] = {}

    for event in transcript["events"]:
        etype = event["type"]
        if etype == "narration":
            emit("educator", "proposal", event["text"], ["walkthrough", *base_tags])
        elif etype == "question":
            last_question_turn = emit(
                "developer", "question", event["text"], ["voice-qa", *base_tags]
            )
        elif etype == "answer":
            emit(
                "educator",
                "evidence",
                event["text"],
                ["voice-qa", *base_tags],
                reply_to=last_question_turn,
            )
        elif etype == "parked_question":
            parked.append(event["text"])
            emit("developer", "question", event["text"], ["voice-qa", "parked", *base_tags])
        elif etype == "quiz_question":
            qid = event["qid"]
            quiz_meta[qid] = event
            emit(
                "educator",
                "question",
                event["text"],
                ["quiz", f"q:{qid}", f"bloom:{event['bloom_level']}", *base_tags],
            )
        elif etype == "quiz_answer":
            emit(
                "developer",
                "evidence",
                event["text"],
                ["quiz-answer", f"q:{event['qid']}", *base_tags],
            )
        elif etype == "quiz_grade":
            qid = event["qid"]
            meta = quiz_meta[qid]
            score = float(event["score"])
            emit(
                "educator",
                "critique",
                event.get("feedback", f"Score {score:.2f}"),
                ["quiz-grade", f"q:{qid}", *base_tags],
            )
            education_rows.append(
                (meta["bloom_level"], meta["question_type"], score, score >= threshold)
            )
        elif etype == "explain_back_prompt":
            emit("educator", "question", event["text"], ["explain-back", *base_tags])
        elif etype == "explain_back_answer":
            emit("developer", "evidence", event["text"], ["explain-back", *base_tags])
        elif etype == "explain_back_grade":
            score = float(event["score"])
            emit(
                "educator",
                "critique",
                event.get("feedback", f"Score {score:.2f}"),
                ["explain-back", *base_tags],
            )
            education_rows.append(("evaluate", "explain-back", score, score >= threshold))
        elif etype == "deferral":
            emit("facilitator", "decision", event["text"], ["education-deferred", *base_tags])

    # Narration-completed row: makes "walked" queryable (grill D-mapping).
    education_rows.append(("understand", "walkthrough", 1.0, True))

    # All education_results rows land in ONE transaction (review fold): a crash
    # can never leave a partial row set behind the session_id idempotency key.
    # Mirrors scripts/record_education.py's insert exactly.
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executemany(
            """INSERT INTO education_results
               (session_id, discussion_id, bloom_level, question_type,
                score, passed, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    session_id,
                    discussion_id,
                    bloom,
                    qtype,
                    score,
                    passed,
                    datetime.now(UTC).isoformat(),
                )
                for bloom, qtype, score, passed in education_rows
            ],
        )
        conn.commit()
    finally:
        conn.close()
    rows_recorded = len(education_rows)

    if mode == "gate" and registry is not None:
        gate_registry.record_attempt(registry, gate_id, session_id, quiz_average, cleared)
        deferral_events = [e for e in transcript["events"] if e["type"] == "deferral"]
        if cleared:
            gate_registry.clear_gate(registry, gate_id, session_id, discussion_id)
        elif deferral_events:
            gate_registry.redefer_gate(registry, gate_id, deferral_events[0]["text"])
        gate_registry.save_registry(registry, registry_path)

    summary_bits = [
        f"Walkthrough session {session_id} ({mode} mode, client={transcript['client']})",
        f"chapter: {chapter['title']}",
        f"education rows: {rows_recorded}",
        f"quiz average: {quiz_average if quiz_average is not None else 'no quiz'}",
    ]
    if mode == "gate":
        summary_bits.append(f"gate {gate_id}: {'CLEARED' if cleared else 'NOT cleared'}")
    if parked:
        summary_bits.append(f"parked questions for a desk session: {len(parked)}")
    emit(
        "facilitator", "synthesis", " · ".join(summary_bits), ["education", "results", *base_tags]
    )

    if close:
        try:
            seal_discussion(discussion_id)
        except Exception as exc:  # noqa: BLE001 — sealing is best-effort; ingest already succeeded
            print(
                f"Warning: discussion sealing failed ({type(exc).__name__}); "
                "ingest itself is complete."
            )

    return {
        "skipped": False,
        "discussion_id": discussion_id,
        "rows_recorded": rows_recorded,
        "gate_id": gate_id,
        "gate_cleared": cleared if mode == "gate" else None,
        "quiz_average": quiz_average,
        "parked_questions": parked,
    }


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Ingest a walkthrough-session transcript")
    parser.add_argument("transcript", type=Path, help="Path to the transcript JSON")
    parser.add_argument("--no-close", action="store_true", help="Skip sealing the discussion")
    args = parser.parse_args()

    try:
        with open(args.transcript, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Could not read transcript: {type(exc).__name__}")
        sys.exit(1)

    try:
        result = ingest(data, close=not args.no_close)
    except (TranscriptError, gate_registry.RegistryError) as exc:
        print(str(exc))
        sys.exit(1)

    if result["skipped"]:
        print(f"Skipped: {result['reason']}")
        return
    print(f"Ingested into {result['discussion_id']} ({result['rows_recorded']} education rows)")
    if result["gate_id"]:
        status = "CLEARED" if result["gate_cleared"] else "NOT cleared (attempt recorded)"
        print(f"Gate {result['gate_id']}: {status}")
    for question in result["parked_questions"]:
        print(f"Parked question: {question}")


if __name__ == "__main__":
    main()
