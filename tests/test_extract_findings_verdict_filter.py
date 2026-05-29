"""Regression: scripts/extract_findings.py verdict-boilerplate filter (F2).

Bug (BUILD_STATUS 2026-05-28, meta-review adjustment A'): extract_findings accepted
every ``critique``/``proposal`` intent event, with the only filter skipping facilitator
``context-brief``/``build-plan`` tags. Synthesis verdict headers and round/confidence
markers therefore got recorded as findings — e.g. "## Verdict: APPROVE WITH CHANGES
(confidence 0.82)", "round 2: approve", bare "REVISE", "Confidence 0.91". Because
``_extract_summary`` takes the first line/sentence verbatim and ``pattern_hash`` consumes
that summary, these polluted the severity histogram and produced phantom verdict-header
promotion candidates (this hub's 3 candidates were all verdict headers).

These tests guard the filter at the extraction boundary. They would FAIL under the old
code, which recorded a finding for every critique/proposal event regardless of content.

Do not delete or weaken without explicit developer approval (testing_requirements.md).

Isolation: each test builds a fresh canonical-schema DB via ``init_db()`` in ``tmp_path``
and a throwaway discussion tree, then monkeypatches ``DB_PATH`` and ``DISCUSSIONS_DIR`` on
the module under test. ``extract_findings`` reads both as module globals at call time.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

# Add project root to path so we can import scripts.*
TEMPLATE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(TEMPLATE_ROOT))

from scripts import extract_findings as ef_module  # noqa: E402
from scripts.extract_findings import (  # noqa: E402
    _extract_summary,
    _is_verdict_boilerplate,
    extract_findings,
)
from scripts.init_db import init_db  # noqa: E402

pytestmark = pytest.mark.regression


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_discussion(discussions_dir: Path, discussion_id: str, events: list[dict]) -> None:
    """Create discussions/<date>/<discussion_id>/events.jsonl with the given events."""
    disc_dir = discussions_dir / "2026-05-28" / discussion_id
    disc_dir.mkdir(parents=True, exist_ok=True)
    with open(disc_dir / "events.jsonl", "w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")


@pytest.fixture()
def pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Fresh DB + discussions tree, routed into the extract_findings module."""
    db_path = tmp_path / "evaluation.db"
    init_db(db_path)
    discussions_dir = tmp_path / "discussions"
    discussions_dir.mkdir()
    monkeypatch.setattr(ef_module, "DB_PATH", db_path)
    monkeypatch.setattr(ef_module, "DISCUSSIONS_DIR", discussions_dir)

    # init_db only creates the schema; findings carry a FK to discussions, so seed the row.
    def register(discussion_id: str) -> None:
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO discussions "
            "(discussion_id, created_at, risk_level, collaboration_mode) "
            "VALUES (?, '2026-05-28T00:00:00+00:00', 'medium', 'ensemble')",
            (discussion_id,),
        )
        conn.commit()
        conn.close()

    def count_findings(discussion_id: str) -> int:
        conn = sqlite3.connect(str(db_path))
        n = conn.execute(
            "SELECT COUNT(*) FROM findings WHERE discussion_id = ?", (discussion_id,)
        ).fetchone()[0]
        conn.close()
        return n

    return discussions_dir, register, count_findings


# ---------------------------------------------------------------------------
# Boilerplate-shape catalogue (sampled verbatim from live discussion events)
# ---------------------------------------------------------------------------

# Pure verdict / round / confidence boilerplate — these MUST be filtered out. The string
# here is the *summary* (first line/sentence), which is what the filter actually sees.
_BOILERPLATE_SUMMARIES = [
    "## Verdict: APPROVE WITH CHANGES (confidence: 0.82)",
    "### Verdict: APPROVE-WITH-CHANGES (confidence: 0.87)",
    "Verdict: APPROVE WITH CHANGES (confidence: 0.88)",
    "Verdict: REVISE",
    "Verdict: REQUEST-CHANGES",
    "round 2: approve",
    "APPROVE Round 2",
    "APPROVE (Round 2)",
    "approve-with-changes",
    "request-changes",
    "REVISE",
    "Confidence 0.91",
    # Bare pass/fail verdict tokens (A2 — both directions guarded against _VERDICT_TOKENS drift).
    "PASS",
    "FAIL",
    "pass",
    "fail",
]

# Verdict-PREFIXED lines that carry substantive text, plus ordinary findings — these MUST
# survive (proof the filter does not over-reach).
_SUBSTANTIVE_SUMMARIES = [
    "REVISE: tests/ classification gap — commit_protocol.md requires /review for tests",
    "APPROVE: All subprocess calls use list-form arguments (no shell=True)",
    "Missing validation on the discussion_id parameter allows path traversal",
    "Race condition in the connection pool under concurrent writes",
    # pass/fail as ordinary English words in a finding must NOT be filtered (A2).
    "FAIL: coverage dropped below the 80% threshold on the new module",
    "Tests fail when the DB path is missing — the FileNotFoundError is unhandled",
]

# Empty / whitespace-only summaries: the predicate does NOT treat these as boilerplate
# (A1); the empty-summary drop is the extraction loop's responsibility, tested end-to-end
# in test_empty_content_events_yield_zero_findings.
_NON_BOILERPLATE_EMPTY = ["", "   ", "\t"]


# ---------------------------------------------------------------------------
# Unit tests on the predicate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("summary", _BOILERPLATE_SUMMARIES)
def test_verdict_boilerplate_is_detected(summary: str) -> None:
    assert _is_verdict_boilerplate(summary) is True


@pytest.mark.parametrize("summary", _SUBSTANTIVE_SUMMARIES)
def test_substantive_finding_is_not_boilerplate(summary: str) -> None:
    assert _is_verdict_boilerplate(summary) is False


@pytest.mark.parametrize("summary", _NON_BOILERPLATE_EMPTY)
def test_empty_summary_is_not_treated_as_boilerplate(summary: str) -> None:
    # The predicate documents that empty/whitespace handling is the caller's job (A1).
    assert _is_verdict_boilerplate(summary) is False


def test_verdict_header_crossing_truncation_boundary_is_detected() -> None:
    # A verdict header longer than the 200-char _extract_summary cutoff is still detected,
    # because the patterns anchor at the start and truncation only affects the tail (A4).
    long_header = "## Verdict: APPROVE WITH CHANGES " + "x " * 120
    summary = _extract_summary(long_header)
    assert len(summary) <= 200
    assert _is_verdict_boilerplate(summary) is True


# ---------------------------------------------------------------------------
# End-to-end extraction tests
# ---------------------------------------------------------------------------


def test_verdict_line_critique_events_yield_zero_findings(pipeline) -> None:
    """A discussion whose only critique/proposal events are verdict lines records 0 findings.

    Under the old code (no verdict filter) every one of these events produced a finding.
    """
    discussions_dir, register, count_findings = pipeline
    discussion_id = "DISC-20260528-000001-verdicts"
    register(discussion_id)
    events = [
        {
            "intent": "critique",
            "agent": "facilitator",
            "turn_id": i,
            "tags": [],
            "content": content,
        }
        for i, content in enumerate(
            [
                "## Verdict: APPROVE WITH CHANGES (confidence: 0.82)\n\n### Blocking\n1. x",
                "Verdict: REVISE. 7 findings (2 medium, 5 low/info). BLOCKING: (1) thing",
                "round 2: approve",
                "APPROVE Round 2. ADR-0005 sequencing accepted. Format asymmetry intentional.",
                "Confidence 0.91. Structural alignment is sound.",
            ]
        )
    ]
    _write_discussion(discussions_dir, discussion_id, events)

    result = extract_findings(discussion_id)

    assert result == 0
    assert count_findings(discussion_id) == 0


def test_substantive_findings_still_recorded(pipeline) -> None:
    """Real findings (including verdict-prefixed substantive lines) are not over-filtered."""
    discussions_dir, register, count_findings = pipeline
    discussion_id = "DISC-20260528-000002-real"
    register(discussion_id)
    events = [
        {
            "intent": "critique",
            "agent": "security-specialist",
            "turn_id": 1,
            "tags": [],
            "content": "Missing validation on the discussion_id parameter allows path traversal.",
        },
        {
            "intent": "critique",
            "agent": "independent-perspective",
            "turn_id": 2,
            "tags": [],
            "content": "REVISE: tests/ classification gap — /review required for tests changes.",
        },
    ]
    _write_discussion(discussions_dir, discussion_id, events)

    result = extract_findings(discussion_id)

    assert result == 2
    assert count_findings(discussion_id) == 2


def test_mixed_events_record_only_substantive_findings(pipeline) -> None:
    """A realistic mix: verdict header dropped, the substantive finding kept."""
    discussions_dir, register, count_findings = pipeline
    discussion_id = "DISC-20260528-000003-mixed"
    register(discussion_id)
    events = [
        {
            "intent": "proposal",
            "agent": "facilitator",
            "turn_id": 1,
            "tags": [],
            "content": "## Verdict: APPROVE WITH CHANGES (confidence: 0.78)\n\n### Blocking\n1. y",
        },
        {
            "intent": "critique",
            "agent": "qa-specialist",
            "turn_id": 2,
            "tags": [],
            "content": "Missing test coverage for the empty-events branch in extract_findings.",
        },
    ]
    _write_discussion(discussions_dir, discussion_id, events)

    result = extract_findings(discussion_id)

    assert result == 1
    assert count_findings(discussion_id) == 1


def test_empty_content_events_yield_zero_findings(pipeline) -> None:
    """Events with empty/missing content produce no blank-summary findings (A1).

    Under the pre-guard code these wrote rows with an empty summary, severity='medium',
    category='general' — silent corpus pollution.
    """
    discussions_dir, register, count_findings = pipeline
    discussion_id = "DISC-20260528-000004-empty"
    register(discussion_id)
    events = [
        {"intent": "critique", "agent": "qa-specialist", "turn_id": 1, "tags": [], "content": ""},
        {
            "intent": "proposal",
            "agent": "qa-specialist",
            "turn_id": 2,
            "tags": [],
        },  # no content key
        {
            "intent": "critique",
            "agent": "qa-specialist",
            "turn_id": 3,
            "tags": [],
            "content": "   ",
        },
    ]
    _write_discussion(discussions_dir, discussion_id, events)

    result = extract_findings(discussion_id)

    assert result == 0
    assert count_findings(discussion_id) == 0
