"""Education gate registry — library + CLI.

Tracks education gates (Principle #6: walkthrough -> quiz -> explain-back -> merge)
that were *deferred* at review/merge time and are still awaiting closure. The registry
is a single YAML file (default: ``docs/education/gates.yaml``) with a validated schema.

Schema (version 1)::

    version: 1
    gates:
      - gate_id: EDU-20260610-unit-4-1   # charset [A-Za-z0-9._-]+, unique
        created_at: "2026-06-10"          # ISO date the deferral was logged
        origin: REV-20260610-012629       # REV id / handoff session / walkthrough doc
        branch: feat/...                  # optional
        scope:
          files: [<paths>]
          adrs: [<ADR ids>]               # may be empty
          spec: <SPEC id or null>
        reason_deferred: <one-line reason>
        status: open                      # open | cleared | re-deferred
        cleared_by: null                  # or {session_id, discussion_id, cleared_at}
        clear_eligible:                   # OPTIONAL, additive (ADR-0035): a passing
          session_id: ...                 #   education session is on record and the gate
          discussion_id: ...              #   awaits the DEVELOPER'S OWN `clear`. Status
          eligible_at: ...                #   stays `open` — eligible is NOT cleared; the
                                          #   validator rejects the marker on a cleared
                                          #   gate; clear / re-defer remove it.

CLI::

    python scripts/education/gate_registry.py list [--status open] [--eligible]
    python scripts/education/gate_registry.py backlog [--today YYYY-MM-DD]
    python scripts/education/gate_registry.py add --gate-id ... --created-at ... \
        --origin ... --reason ... [--file f ...] [--adr a ...] [--spec s] [--branch b]
    python scripts/education/gate_registry.py clear --gate-id ... \
        --session-id ... --discussion-id ... [--cleared-at ...]
    python scripts/education/gate_registry.py re-defer --gate-id ... --reason ...

``backlog`` is the read-only, age-bucketed rendering consumed by the SessionStart hook
(``.claude/hooks/session-start.ps1``). That hook does not run on every session: **which
SessionStart events run it is set by the matcher in .claude/settings.json** (a protected
file this module cannot read at import time and must not assume). Measured 2026-08-09 the
matcher was ``resume|compact``, i.e. the backlog surfaced on resume/compaction but not on a
fresh session; check the file rather than trusting that date.

``backlog`` is **informational only**: it never writes, never exits non-zero on a missing or
corrupt registry, and nothing in the framework fails because a gate is open (see
``docs/education/governance-mechanisms.md`` Row 6 — turning Principle #5 into a build
condition is a governance change that needs its own /plan and Steward gate).

OWED-DEBT: docs/education/governance-mechanisms.md Row 6 — that row's sentences "Nothing
**warns** either.", "Nothing notices." and "Visibility that depends on somebody choosing to
look is ... the only one operating here." predate this rendering and are now false on the
SessionStart events the matcher selects. That file is outside this module's change scope.
The debt is not recorded only here: ``tests/test_education_backlog_surfacing.py::
TestGovernanceBoundary::test_governance_doc_debt_and_its_acknowledgement_stay_in_sync``
fails if the doc is corrected while these notes remain, or if these notes are deleted while
the doc is still false.

What ``backlog`` asks for, and why in that order: the action line names **/walkthrough then
/quiz** first, because that is where a gate is actually *closed*; ``clear`` is named second
and explicitly as bookkeeping. :func:`clear_gate` writes ``--session-id``/``--discussion-id``
through as opaque strings — it does not check them against ``discussions/``,
``metrics/evaluation.db`` or anything else — so a ``clear``-first nudge would be an
invitation to type invented ids and produce a registry reporting zero education debt with
zero education having happened.

Clearing an already-cleared gate is a deterministic **no-op**: ``clear_gate`` returns
``changed=False`` and leaves the existing ``cleared_by`` untouched. This keeps the
developer's paste and any historical seeding safely idempotent. Since ADR-0035 the
ingest never clears: it records an additive ``clear_eligible`` marker
(:func:`mark_clear_eligible`), and the flip to ``cleared`` is the developer's own
``clear`` CLI action.

**:func:`mark_clear_eligible` is deliberately NOT CLI-exposed** — library-only, no
subcommand, reachable solely through the validated-transcript ingest
(``ingest_walkthrough_session.py``, which writes it only after full schema
validation and a committed evidence transaction). That containment is load-bearing:
a CLI ``mark-eligible`` would be a paste-ready way to mint "paid" markers with no
session behind them, exactly the fabrication surface the clear-first-nudge note
above declines to offer. Do not add the subcommand; if eligibility ever needs a
manual override, that is a design change through the Steward gate, not a flag.

Writes preserve the registry file's leading comment header (see :func:`read_header`).
``yaml.safe_dump`` cannot round-trip comments, so before that was added the first ``clear``
silently deleted the file's seeding provenance. Reproduction command and the measured
line counts are in :func:`read_header` — the short version is that the header went to
**zero** lines, whatever its length.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = PROJECT_ROOT / "docs" / "education" / "gates.yaml"

SCHEMA_VERSION = 1
VALID_STATUSES = ("open", "cleared", "re-deferred")

#: Statuses that mean "this gate is still owed". ``re-deferred`` is included on purpose:
#: a re-deferred gate is unclosed debt, and querying only ``open`` would hide it.
UNCLOSED_STATUSES = ("open", "re-deferred")

#: Age at which the backlog nudge escalates from "[i]" to "[!]". Mirrors the retro-age
#: threshold already used by .claude/hooks/session-start.ps1 (>14 days = overdue).
BACKLOG_ESCALATION_DAYS = 14

#: What actually closes a gate: the education session. Named FIRST in the nudge. Both
#: commands exist as files (pinned by ``tests/test_education_backlog_surfacing.py::
#: TestBacklogSummary::test_nudge_only_names_commands_that_exist``);
#: this constant does not claim either command clears the gate for you.
LEARN_COMMAND_HINT = "/walkthrough then /quiz on that gate's scope"

#: The bookkeeping that RECORDS a completed session. Deliberately second, and deliberately
#: not the headline action: :func:`clear_gate` accepts ``session_id``/``discussion_id`` as
#: opaque strings and validates neither against any store, so a ``clear``-first nudge is an
#: invitation to fabricate a cleared registry in two minutes.
CLEAR_COMMAND_HINT = (
    "python scripts/education/gate_registry.py clear "
    "--gate-id <id> --session-id <id> --discussion-id <id>"
)

#: Longest ``reason_deferred`` excerpt rendered in the nudge before it is truncated. The
#: nudge has to fit the hook's one-line-per-signal PROCESS HEALTH block.
REASON_EXCERPT_CHARS = 110

GATE_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")

# Allowed keys per object. Unknown keys are rejected by the validator.
_REQUIRED_GATE_KEYS = frozenset(
    {"gate_id", "created_at", "origin", "scope", "reason_deferred", "status", "cleared_by"}
)
_OPTIONAL_GATE_KEYS = frozenset({"branch", "clear_eligible"})
_ALLOWED_GATE_KEYS = _REQUIRED_GATE_KEYS | _OPTIONAL_GATE_KEYS

_REQUIRED_SCOPE_KEYS = frozenset({"files", "adrs", "spec"})
_ALLOWED_CLEARED_BY_KEYS = frozenset({"session_id", "discussion_id", "cleared_at"})
#: The additive ADR-0035 marker: a passing session on record, awaiting the developer's
#: own clear. Same shape discipline as cleared_by; carried only on unclosed gates.
_ALLOWED_CLEAR_ELIGIBLE_KEYS = frozenset({"session_id", "discussion_id", "eligible_at"})


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def _is_int(value: Any) -> bool:
    """Return True if value is a real int (bool is rejected — it subclasses int)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_scope(scope: Any, gate_id: str) -> None:
    """Validate a gate's ``scope`` block, raising ValueError on any defect."""
    if not isinstance(scope, dict):
        raise ValueError(f"gate '{gate_id}': scope must be a mapping, got {type(scope).__name__}")
    keys = set(scope)
    missing = _REQUIRED_SCOPE_KEYS - keys
    if missing:
        raise ValueError(f"gate '{gate_id}': scope missing required keys: {sorted(missing)}")
    unknown = keys - _REQUIRED_SCOPE_KEYS
    if unknown:
        raise ValueError(f"gate '{gate_id}': scope has unknown keys: {sorted(unknown)}")
    if not isinstance(scope["files"], list):
        raise ValueError(f"gate '{gate_id}': scope.files must be a list")
    if not isinstance(scope["adrs"], list):
        raise ValueError(f"gate '{gate_id}': scope.adrs must be a list")
    spec = scope["spec"]
    if spec is not None and not isinstance(spec, str):
        raise ValueError(f"gate '{gate_id}': scope.spec must be a string or null")


def _validate_cleared_by(cleared_by: Any, gate_id: str, status: str) -> None:
    """Validate the ``cleared_by`` field against ``status``."""
    if cleared_by is None:
        if status == "cleared":
            raise ValueError(f"gate '{gate_id}': status 'cleared' requires a cleared_by record")
        return
    if not isinstance(cleared_by, dict):
        raise ValueError(f"gate '{gate_id}': cleared_by must be a mapping or null")
    missing = _ALLOWED_CLEARED_BY_KEYS - set(cleared_by)
    if missing:
        raise ValueError(f"gate '{gate_id}': cleared_by missing keys: {sorted(missing)}")
    unknown = set(cleared_by) - _ALLOWED_CLEARED_BY_KEYS
    if unknown:
        raise ValueError(f"gate '{gate_id}': cleared_by has unknown keys: {sorted(unknown)}")


def _validate_clear_eligible(clear_eligible: Any, gate_id: str, status: str) -> None:
    """Validate the optional ``clear_eligible`` marker against its gate's ``status``."""
    if clear_eligible is None:
        return
    if not isinstance(clear_eligible, dict):
        raise ValueError(f"gate '{gate_id}': clear_eligible must be a mapping or null")
    if status == "cleared":
        # Eligible is NOT cleared, and a marker surviving the clear is the exact
        # read-as-cleared drift ADR-0035's naming risk warns about.
        raise ValueError(
            f"gate '{gate_id}': a cleared gate may not carry a clear_eligible marker "
            "(clear_gate removes it; cleared_by is the clearing record)"
        )
    missing = _ALLOWED_CLEAR_ELIGIBLE_KEYS - set(clear_eligible)
    if missing:
        raise ValueError(f"gate '{gate_id}': clear_eligible missing keys: {sorted(missing)}")
    unknown = set(clear_eligible) - _ALLOWED_CLEAR_ELIGIBLE_KEYS
    if unknown:
        raise ValueError(f"gate '{gate_id}': clear_eligible has unknown keys: {sorted(unknown)}")
    for key in sorted(_ALLOWED_CLEAR_ELIGIBLE_KEYS):
        if not isinstance(clear_eligible[key], str):
            raise ValueError(f"gate '{gate_id}': clear_eligible.{key} must be a string")


def validate_gate(gate: Any) -> None:
    """Validate a single gate mapping in place, raising ValueError on any defect.

    Args:
        gate: The candidate gate mapping.

    Raises:
        ValueError: If the gate is not a mapping, is missing or has unknown keys,
            has an invalid ``gate_id`` charset, an out-of-enum ``status``, or a
            malformed / cleared-gate ``clear_eligible`` marker.
    """
    if not isinstance(gate, dict):
        raise ValueError(f"gate must be a mapping, got {type(gate).__name__}")
    keys = set(gate)
    missing = _REQUIRED_GATE_KEYS - keys
    if missing:
        raise ValueError(f"gate missing required keys: {sorted(missing)}")
    unknown = keys - _ALLOWED_GATE_KEYS
    if unknown:
        raise ValueError(f"gate has unknown keys: {sorted(unknown)}")

    gate_id = gate["gate_id"]
    if not isinstance(gate_id, str) or not GATE_ID_RE.match(gate_id):
        raise ValueError(
            f"invalid gate_id {gate_id!r}: must match [A-Za-z0-9._-]+ and be a string"
        )
    for field in ("created_at", "origin", "reason_deferred"):
        if not isinstance(gate[field], str):
            raise ValueError(f"gate '{gate_id}': {field} must be a string")
    if "branch" in gate and not isinstance(gate["branch"], str):
        raise ValueError(f"gate '{gate_id}': branch must be a string")

    status = gate["status"]
    if status not in VALID_STATUSES:
        raise ValueError(
            f"gate '{gate_id}': invalid status {status!r}; must be one of {list(VALID_STATUSES)}"
        )
    _validate_scope(gate["scope"], gate_id)
    _validate_cleared_by(gate["cleared_by"], gate_id, status)
    _validate_clear_eligible(gate.get("clear_eligible"), gate_id, status)


def validate_registry(registry: Any) -> dict[str, Any]:
    """Validate a fully-loaded registry mapping, raising ValueError on any defect.

    Args:
        registry: The parsed registry object.

    Returns:
        The same mapping, once validated.

    Raises:
        ValueError: On a non-mapping root, missing ``version``/``gates`` keys, a
            non-int ``version``, a non-list ``gates``, a duplicate ``gate_id``, or any
            per-gate schema violation.
    """
    if not isinstance(registry, dict):
        raise ValueError(f"registry root must be a mapping, got {type(registry).__name__}")
    if "version" not in registry:
        raise ValueError("registry missing required key: version")
    if "gates" not in registry:
        raise ValueError("registry missing required key: gates")
    if not _is_int(registry["version"]):
        raise ValueError(f"registry version must be an int, got {registry['version']!r}")
    gates = registry["gates"]
    if not isinstance(gates, list):
        raise ValueError(f"registry gates must be a list, got {type(gates).__name__}")

    seen: set[str] = set()
    for gate in gates:
        validate_gate(gate)
        gid = gate["gate_id"]
        if gid in seen:
            raise ValueError(f"duplicate gate_id: {gid!r}")
        seen.add(gid)
    return registry


# --------------------------------------------------------------------------- #
# Load / save
# --------------------------------------------------------------------------- #
def load_registry(path: Path | str = DEFAULT_REGISTRY_PATH) -> dict[str, Any]:
    """Load and validate the registry from ``path``.

    Args:
        path: Path to the registry YAML file.

    Returns:
        The validated registry mapping (``{"version": int, "gates": [...]}``).

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If the file is not valid YAML, is not a mapping, or violates
            the schema.
    """
    path = Path(path)
    with open(path, encoding="utf-8") as handle:
        try:
            data = yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            raise ValueError(f"registry file is not valid YAML: {path}: {exc}") from exc
    if data is None:
        raise ValueError(f"registry file is empty: {path}")
    return validate_registry(data)


def read_header(path: Path | str) -> str:
    """Return the leading comment block of an existing registry file, or ``""``.

    The header is every line from the top of the file that is blank or starts with
    ``#``, stopping at the first line of YAML content. ``yaml.safe_dump`` cannot
    round-trip comments, so :func:`save_registry` re-emits this block verbatim ahead of
    the serialised body; without it the first write silently destroys the file's
    provenance.

    Reproduced 2026-08-09 against commit ``31bfe09`` (the last commit before this change),
    on copies in a scratch directory — never against the live registry::

        git show 31bfe09:scripts/education/gate_registry.py > /tmp/writer.py
        git show 31bfe09:docs/education/gates.yaml          > /tmp/gates.yaml
        python /tmp/writer.py --registry /tmp/gates.yaml clear \
            --gate-id EDU-20260610-unit-3-3 --session-id T --discussion-id T

    ``/tmp/gates.yaml``'s comment header went from **16 lines to 0**, taking the seeding
    provenance and the CLI usage block with it. 16 is that commit's header length, not a
    constant: ``git show 31bfe09:docs/education/gates.yaml | grep -n '^version:'`` prints
    ``17:version: 1``. The invariant the tests pin is the qualitative one — a naive
    ``yaml.safe_dump`` write takes *any* header to zero — and it is pinned without needing
    git, by ``tests/test_gate_registry.py::TestHeaderPreservation``.

    Args:
        path: Path to a registry file. A missing or unreadable file yields ``""``.

    Returns:
        The header text, newline-terminated, or ``""`` if the file does not exist or
        does not begin with a comment.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return ""
    kept: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.strip() and not line.lstrip().startswith("#"):
            break
        kept.append(line)
    header = "".join(kept)
    # A file that opens with blank lines has no header, only whitespace.
    if not header.lstrip().startswith("#"):
        return ""
    return header if header.endswith("\n") else header + "\n"


def save_registry(registry: dict[str, Any], path: Path | str = DEFAULT_REGISTRY_PATH) -> None:
    """Validate then atomically write the registry to ``path``.

    The write goes to a temporary file in the same directory and is moved into place
    with ``os.replace`` so a reader never observes a half-written file. Any leading
    comment header already at ``path`` is preserved verbatim (see :func:`read_header`),
    so clearing a gate does not delete the registry's documentation.

    Args:
        registry: The registry mapping to persist.
        path: Destination path.

    Raises:
        ValueError: If ``registry`` fails schema validation (nothing is written).
    """
    validate_registry(registry)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = read_header(path) + yaml.safe_dump(
        registry, sort_keys=False, default_flow_style=False, allow_unicode=True
    )
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


# --------------------------------------------------------------------------- #
# Query / mutate (operate on an in-memory registry mapping)
# --------------------------------------------------------------------------- #
def list_gates(registry: dict[str, Any], status: str | None = None) -> list[dict[str, Any]]:
    """Return gates, optionally filtered by ``status``.

    Args:
        registry: A validated registry mapping.
        status: If given, only gates with this status are returned.

    Returns:
        A list of gate mappings (a new list; the gate dicts are shared, not copied).

    Raises:
        ValueError: If ``status`` is not a valid status value.
    """
    if status is not None and status not in VALID_STATUSES:
        raise ValueError(
            f"invalid status filter {status!r}; must be one of {list(VALID_STATUSES)}"
        )
    gates: list[dict[str, Any]] = registry["gates"]
    if status is None:
        return list(gates)
    return [g for g in gates if g["status"] == status]


def _parse_created_at(value: Any) -> date | None:
    """Return ``created_at`` as a date, or None if it is not parseable.

    The schema only requires ``created_at`` to be a *string*, so an unparseable value is a
    legal registry that the backlog rendering must survive rather than reject.

    Args:
        value: The raw ``created_at`` field.

    Returns:
        The parsed date, or None.
    """
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _one_line_excerpt(value: Any, limit: int = REASON_EXCERPT_CHARS) -> str:
    """Flatten and truncate registry-supplied free text for single-line hook output.

    ``reason_deferred`` is prose typed by whoever logged the deferral and it crosses a
    trust boundary here: it is interpolated into the stdout of a PowerShell hook whose
    format is one line per signal. Newlines, tabs and non-printable characters are removed
    so a multi-line reason cannot break that block — the same reasoning that makes
    :func:`_cmd_backlog` print only an exception *class* and not its message. Truncation
    uses ASCII ``...`` rather than an ellipsis character because the consumer is a Windows
    PowerShell 5.1 console with a code page this module cannot assume.

    Args:
        value: The raw field. A non-string (a legal shape for the hook's tolerant read)
            yields ``""``.
        limit: Maximum characters before truncation.

    Returns:
        A single-line excerpt, possibly empty.
    """
    if not isinstance(value, str):
        return ""
    flat = " ".join(value.split())
    flat = "".join(char for char in flat if char.isprintable())
    if len(flat) <= limit:
        return flat
    return flat[: max(limit - 3, 0)].rstrip() + "..."


def backlog_summary(registry: dict[str, Any], today: date | None = None) -> list[str]:
    """Render unclosed education gates as informational session-start lines.

    Read-only. Returns an empty list when nothing is owed, so a clean registry produces
    no session-start noise at all. Lines are indented two spaces to sit inside the hook's
    PROCESS HEALTH block, and carry no exit-code or blocking meaning.

    The rendering names one gate — the *focus* gate, the oldest one whose ``created_at``
    parses, else the first unclosed one — and quotes its ``reason_deferred``. A bare count
    of gate ids ("7 open gates", ``EDU-20260610-unit-3-3``) is a number the reader learns
    to skip; the reason is the sentence that makes it a decision they can act on. This
    line recurs on every matching session for as long as the backlog stands, so it has to
    carry a specific request rather than a tally.

    Since ADR-0035 the unclosed set splits in two, and collapsing them was measured
    as a real regression (a gate the developer walked and quizzed at 0.9 rendered
    byte-identically to one nobody opened): **unpaid** gates get the four learning
    lines below, and **clear-eligible** gates — paid, awaiting the DEVELOPER'S own
    clear — get their own bucket that asks for the paste, not for re-learning.
    Eligible gates stay inside this debt block on purpose: eligible is not cleared.

    Args:
        registry: A validated registry mapping.
        today: Date to age gates against (defaults to the local current date).

    Returns:
        Zero lines (nothing unclosed). Otherwise: for unpaid gates, exactly four
        lines — a headline with the counts and the focus gate, what that gate owes,
        the action that CLOSES it (an education session), and the bookkeeping that
        RECORDS that session (learning before bookkeeping on purpose — see
        :data:`CLEAR_COMMAND_HINT`); plus, when clear-eligible gates exist, two
        more — their count/focus and the ``list --eligible`` re-print pointer.
    """
    today = today or date.today()
    unclosed = [g for g in registry["gates"] if g["status"] in UNCLOSED_STATUSES]
    if not unclosed:
        return []

    eligible = [g for g in unclosed if g.get("clear_eligible")]
    gates = [g for g in unclosed if not g.get("clear_eligible")]
    if not gates:
        return _eligible_lines(eligible)

    ages: list[tuple[int, dict[str, Any]]] = []
    unknown_age = 0
    for gate in gates:
        created = _parse_created_at(gate.get("created_at"))
        if created is None:
            unknown_age += 1
        else:
            ages.append(((today - created).days, gate))

    re_deferred = sum(1 for g in gates if g["status"] == "re-deferred")

    if ages:
        oldest_days, focus = max(ages, key=lambda pair: pair[0])
        over = sum(1 for days, _ in ages if days > BACKLOG_ESCALATION_DAYS)
        marker = "[!]" if oldest_days > BACKLOG_ESCALATION_DAYS else "[i]"
        headline = (
            f"  {marker} EDUCATION DEBT: {len(gates)} education gate(s) deferred and never "
            f"cleared; oldest {oldest_days} days ({focus['gate_id']}). "
            f"{over} over {BACKLOG_ESCALATION_DAYS} days."
        )
    else:
        focus = gates[0]
        headline = (
            f"  [i] EDUCATION DEBT: {len(gates)} education gate(s) deferred and never "
            f"cleared ({focus['gate_id']}). No parseable created_at on any of them."
        )

    if re_deferred:
        headline += f" {re_deferred} re-deferred."
    if unknown_age and ages:
        headline += f" {unknown_age} with unparseable created_at."

    reason = _one_line_excerpt(focus.get("reason_deferred"))
    owed = (
        f'      It owes: "{reason}"'
        if reason
        else "      It records no reason_deferred; check it with `gate_registry.py list`."
    )
    action = (
        f"      Close it by learning it: {LEARN_COMMAND_HINT}. Nothing fails on an open "
        f"gate -- Principle #5 is human-held."
    )
    record = (
        f"      Then record that session -- clearing records a session, it cannot replace "
        f"one: {CLEAR_COMMAND_HINT}"
    )
    return [headline, owed, action, record] + _eligible_lines(eligible)


def _eligible_lines(eligible: list[dict[str, Any]]) -> list[str]:
    """Render the clear-eligible bucket: paid debt awaiting the developer's clear.

    Two lines (or zero). Deliberately NOT the learning nudge — these gates were
    paid; asking the developer to re-learn them is the exact confusion the
    ``clear_eligible`` marker exists to remove. The paste-ready commands are
    re-printable at any time via ``list --eligible``, so eligibility does not die
    with the ingest's console.
    """
    if not eligible:
        return []
    focus = eligible[0]
    return [
        f"  [i] {len(eligible)} education gate(s) CLEAR-ELIGIBLE -- paid, awaiting YOUR "
        f"clear ({focus['gate_id']}). Eligible is not cleared until you run it.",
        "      Re-print the paste-ready command(s): "
        "python scripts/education/gate_registry.py list --eligible",
    ]


def get_gate(registry: dict[str, Any], gate_id: str) -> dict[str, Any]:
    """Return the gate with ``gate_id``.

    Args:
        registry: A validated registry mapping.
        gate_id: The gate to fetch.

    Returns:
        The matching gate mapping.

    Raises:
        KeyError: If no gate with ``gate_id`` exists.
    """
    for gate in registry["gates"]:
        if gate["gate_id"] == gate_id:
            return gate
    raise KeyError(f"no gate with gate_id {gate_id!r}")


def add_gate(
    registry: dict[str, Any],
    *,
    gate_id: str,
    created_at: str,
    origin: str,
    reason_deferred: str,
    files: list[str] | None = None,
    adrs: list[str] | None = None,
    spec: str | None = None,
    branch: str | None = None,
    status: str = "open",
) -> dict[str, Any]:
    """Append a new gate to ``registry`` and return it.

    Args:
        registry: A validated registry mapping (mutated in place).
        gate_id: Stable, unique id matching ``[A-Za-z0-9._-]+``.
        created_at: ISO date the deferral was logged.
        origin: Where the deferral was recorded (REV id / session / doc path).
        reason_deferred: One-line reason.
        files: Scope file paths (default empty).
        adrs: Scope ADR ids (default empty).
        spec: Scope SPEC id, or None.
        branch: Optional branch the gate covers.
        status: Initial status (default ``open``).

    Returns:
        The newly-created gate mapping.

    Raises:
        ValueError: If ``gate_id`` already exists or the gate fails validation.
    """
    if any(g["gate_id"] == gate_id for g in registry["gates"]):
        raise ValueError(f"gate_id already exists: {gate_id!r}")
    gate: dict[str, Any] = {
        "gate_id": gate_id,
        "created_at": created_at,
        "origin": origin,
    }
    if branch is not None:
        gate["branch"] = branch
    gate["scope"] = {"files": list(files or []), "adrs": list(adrs or []), "spec": spec}
    gate["reason_deferred"] = reason_deferred
    gate["status"] = status
    gate["cleared_by"] = None
    validate_gate(gate)
    registry["gates"].append(gate)
    return gate


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(UTC).isoformat()


def clear_gate(
    registry: dict[str, Any],
    gate_id: str,
    session_id: str,
    discussion_id: str,
    cleared_at: str | None = None,
) -> tuple[dict[str, Any], bool]:
    """Mark a gate cleared. Idempotent: clearing an already-cleared gate is a no-op.

    Args:
        registry: A validated registry mapping (mutated in place on a real clear).
        gate_id: The gate to clear.
        session_id: Education session that closed the gate.
        discussion_id: Discussion id that closed the gate.
        cleared_at: ISO timestamp of closure (default: current UTC time).

    Returns:
        ``(gate, changed)`` where ``changed`` is False if the gate was already cleared
        (in which case the existing ``cleared_by`` is left untouched).

    Raises:
        KeyError: If no gate with ``gate_id`` exists.
    """
    gate = get_gate(registry, gate_id)
    if gate["status"] == "cleared":
        return gate, False
    gate["status"] = "cleared"
    gate["cleared_by"] = {
        "session_id": session_id,
        "discussion_id": discussion_id,
        "cleared_at": cleared_at or _utc_now_iso(),
    }
    # The eligibility marker is subsumed by cleared_by; a marker surviving the
    # clear would read as a second, contradictory claim (ADR-0035 naming risk).
    gate.pop("clear_eligible", None)
    return gate, True


def re_defer_gate(registry: dict[str, Any], gate_id: str, reason: str) -> dict[str, Any]:
    """Re-defer a gate: set status ``re-deferred`` and update the reason.

    Any prior ``cleared_by`` record is dropped (the gate is no longer cleared).

    Args:
        registry: A validated registry mapping (mutated in place).
        gate_id: The gate to re-defer.
        reason: New one-line reason for the re-deferral.

    Returns:
        The updated gate mapping.

    Raises:
        KeyError: If no gate with ``gate_id`` exists.
    """
    gate = get_gate(registry, gate_id)
    gate["status"] = "re-deferred"
    gate["reason_deferred"] = reason
    gate["cleared_by"] = None
    # A re-deferred gate is unpaid again by definition; a stale eligibility marker
    # would invite a paste that clears unlearned debt (ADR-0035).
    gate.pop("clear_eligible", None)
    return gate


def mark_clear_eligible(
    registry: dict[str, Any],
    gate_id: str,
    session_id: str,
    discussion_id: str,
    eligible_at: str | None = None,
) -> tuple[dict[str, Any], bool]:
    """Record that a passing education session awaits the developer's own clear.

    ADDITIVE (ADR-0035): sets the optional ``clear_eligible`` marker and touches
    nothing else — ``status`` stays as it is, ``cleared``/``cleared_by`` remain
    reachable only through :func:`clear_gate` (the developer's action). A later
    eligible session overwrites an earlier marker (latest session wins).

    Args:
        registry: A validated registry mapping (mutated in place).
        gate_id: The gate the session paid.
        session_id: The education session establishing eligibility.
        discussion_id: The discussion holding the session's evidence.
        eligible_at: ISO timestamp (default: current UTC time).

    Returns:
        ``(gate, changed)`` — ``changed`` is False when the gate is already
        cleared (nothing to await; the marker is not written).

    Raises:
        KeyError: If no gate with ``gate_id`` exists.
    """
    gate = get_gate(registry, gate_id)
    if gate["status"] == "cleared":
        return gate, False
    gate["clear_eligible"] = {
        "session_id": session_id,
        "discussion_id": discussion_id,
        "eligible_at": eligible_at or _utc_now_iso(),
    }
    return gate, True


def clear_command_for(gate: dict[str, Any], registry_path: Path | str | None = None) -> str | None:
    """The paste-ready DEVELOPER command for an eligible gate, or ``None``.

    Interpolates ``--registry`` (quoted) whenever ``registry_path`` names a file
    other than :data:`DEFAULT_REGISTRY_PATH`, so a command minted against a
    non-default registry never silently mutates the default one. Both ids were
    validated to ``[A-Za-z0-9._-]+`` at write time, so interpolation cannot
    smuggle flags.

    Args:
        gate: A gate mapping (validated shape).
        registry_path: The registry the command should act on, or ``None`` /
            the default for a plain command.

    Returns:
        The command string, or ``None`` when the gate carries no
        ``clear_eligible`` marker.
    """
    marker = gate.get("clear_eligible")
    if not marker:
        return None
    registry_flag = ""
    if registry_path is not None:
        resolved = Path(registry_path).resolve()
        if resolved != DEFAULT_REGISTRY_PATH.resolve():
            registry_flag = f'--registry "{resolved}" '
    return (
        f"python scripts/education/gate_registry.py {registry_flag}clear "
        f"--gate-id {gate['gate_id']} --session-id {marker['session_id']} "
        f"--discussion-id {marker['discussion_id']}"
    )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _cmd_list(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)
    gates = list_gates(registry, status=args.status)
    if args.eligible:
        # The re-print path (ADR-0035): eligibility must not die with the ingest's
        # console. Recover the DEVELOPER'S paste-ready clear command days later.
        gates = [g for g in gates if g.get("clear_eligible")]
        if not gates:
            print("No clear-eligible gates.")
            return 0
        for gate in gates:
            marker = gate["clear_eligible"]
            print(
                f"{gate['gate_id']}\t{gate['status']}\teligible_at={marker['eligible_at']}"
                f"\tsession={marker['session_id']}"
            )
            print(f"  {clear_command_for(gate, args.registry)}")
        print(f"\n{len(gates)} clear-eligible gate(s). Clearing them is the developer's action.")
        return 0
    if not gates:
        filt = f" (status={args.status})" if args.status else ""
        print(f"No gates{filt}.")
        return 0
    for gate in gates:
        spec = gate["scope"].get("spec") or "-"
        print(f"{gate['gate_id']}\t{gate['status']}\t{gate['origin']}\tspec={spec}")
    print(f"\n{len(gates)} gate(s).")
    return 0


def _cmd_backlog(args: argparse.Namespace) -> int:
    """Print the unclosed-gate nudge. Never fails: always returns 0.

    A missing or corrupt registry prints one diagnostic line instead of raising, because the
    only caller is a SessionStart hook that must never break a session. Only the exception
    *class* is printed -- a YAML parse error's message is multi-line and would wreck the
    hook's single-line block format.
    """
    try:
        registry = load_registry(args.registry)
    except (ValueError, OSError) as exc:  # OSError covers FileNotFoundError/PermissionError
        print(f"  [?] Education gate registry unreadable ({args.registry}): {type(exc).__name__}.")
        print("      Check it with: python scripts/education/gate_registry.py list")
        return 0
    today = date.fromisoformat(args.today) if args.today else None
    for line in backlog_summary(registry, today=today):
        print(line)
    return 0


def _cmd_add(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)
    add_gate(
        registry,
        gate_id=args.gate_id,
        created_at=args.created_at,
        origin=args.origin,
        reason_deferred=args.reason,
        files=args.file,
        adrs=args.adr,
        spec=args.spec,
        branch=args.branch,
        status=args.status,
    )
    save_registry(registry, args.registry)
    print(f"Added gate {args.gate_id} (status={args.status}).")
    return 0


def _cmd_clear(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)
    _gate, changed = clear_gate(
        registry,
        args.gate_id,
        session_id=args.session_id,
        discussion_id=args.discussion_id,
        cleared_at=args.cleared_at,
    )
    if changed:
        save_registry(registry, args.registry)
        print(f"Cleared gate {args.gate_id}.")
    else:
        print(f"Gate {args.gate_id} was already cleared; no change.")
    return 0


def _cmd_re_defer(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)
    re_defer_gate(registry, args.gate_id, reason=args.reason)
    save_registry(registry, args.registry)
    print(f"Re-deferred gate {args.gate_id}.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for the CLI."""
    parser = argparse.ArgumentParser(description="Education gate registry management")
    parser.add_argument(
        "--registry",
        default=str(DEFAULT_REGISTRY_PATH),
        help="Path to the registry YAML (default: docs/education/gates.yaml)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List gates")
    p_list.add_argument("--status", choices=VALID_STATUSES, default=None)
    p_list.add_argument(
        "--eligible",
        action="store_true",
        help="Only clear-eligible gates, with the developer's paste-ready clear command",
    )
    p_list.set_defaults(func=_cmd_list)

    p_backlog = sub.add_parser(
        "backlog", help="Print an age-bucketed unclosed-gate nudge (SessionStart hook; read-only)"
    )
    p_backlog.add_argument(
        "--today",
        default=None,
        help="ISO date to age gates against (test seam; default: today)",
    )
    p_backlog.set_defaults(func=_cmd_backlog)

    p_add = sub.add_parser("add", help="Add a new deferred gate")
    p_add.add_argument("--gate-id", required=True)
    p_add.add_argument("--created-at", required=True, help="ISO date of the deferral")
    p_add.add_argument("--origin", required=True)
    p_add.add_argument("--reason", required=True, help="One-line reason deferred")
    p_add.add_argument("--file", action="append", default=[], help="Scope file (repeatable)")
    p_add.add_argument("--adr", action="append", default=[], help="Scope ADR id (repeatable)")
    p_add.add_argument("--spec", default=None)
    p_add.add_argument("--branch", default=None)
    p_add.add_argument("--status", choices=VALID_STATUSES, default="open")
    p_add.set_defaults(func=_cmd_add)

    p_clear = sub.add_parser("clear", help="Clear a gate (idempotent)")
    p_clear.add_argument("--gate-id", required=True)
    p_clear.add_argument("--session-id", required=True)
    p_clear.add_argument("--discussion-id", required=True)
    p_clear.add_argument("--cleared-at", default=None, help="ISO timestamp (default: now UTC)")
    p_clear.set_defaults(func=_cmd_clear)

    p_redef = sub.add_parser("re-defer", help="Re-defer a gate with a new reason")
    p_redef.add_argument("--gate-id", required=True)
    p_redef.add_argument("--reason", required=True)
    p_redef.set_defaults(func=_cmd_re_defer)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Argument vector (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code (0 on success, 2 on a handled ValueError/KeyError).
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (ValueError, KeyError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
