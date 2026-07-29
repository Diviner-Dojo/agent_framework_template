"""Tests for scripts/audit_calibration.py — the confidence-calibration loop (ADR-0024).

Locks the load-bearing guards from the independent enumeration (DISC-20260613-234253):
is_noise=0 on severity signals, no agent-authored text into a sink, generic DB errors,
no auto-apply (writes only the queue + log), and an append-only proposal queue.
"""

from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import pytest

# Add scripts to path for import
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import audit_calibration  # noqa: E402

_FINDINGS_DDL = """
CREATE TABLE findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discussion_id TEXT NOT NULL,
    turn_id INTEGER NOT NULL,
    agent TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('critical','high','medium','low','info')),
    category TEXT NOT NULL,
    summary TEXT NOT NULL,
    raw_excerpt TEXT,
    resolved BOOLEAN NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL,
    is_noise INTEGER NOT NULL DEFAULT 0
)
"""

_AE_DDL = """
CREATE TABLE agent_effectiveness (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent TEXT NOT NULL,
    discussion_id TEXT NOT NULL,
    findings_unique INTEGER NOT NULL DEFAULT 0,
    findings_duplicate INTEGER NOT NULL DEFAULT 0,
    findings_false_positive INTEGER NOT NULL DEFAULT 0,
    confidence_avg REAL,
    confidence_calibration REAL,
    computed_at DATETIME NOT NULL
)
"""


def _make_db(path: Path, findings: list[dict], ae: list[dict]) -> Path:
    """Build a minimal evaluation.db with the rows under test."""
    conn = sqlite3.connect(str(path))
    conn.execute(_FINDINGS_DDL)
    conn.execute(_AE_DDL)
    for f in findings:
        conn.execute(
            """INSERT INTO findings
               (discussion_id, turn_id, agent, severity, category, summary,
                raw_excerpt, is_noise, created_at)
               VALUES (?, 1, 'qa', ?, ?, ?, NULL, ?, '2026-06-13T00:00:00')""",
            (f.get("disc", "D"), f["severity"], f["category"], f["summary"], f.get("is_noise", 0)),
        )
    for a in ae:
        conn.execute(
            """INSERT INTO agent_effectiveness
               (agent, discussion_id, confidence_calibration, computed_at)
               VALUES (?, ?, ?, '2026-06-13T00:00:00')""",
            (a["agent"], a.get("disc", "D"), a["cal"]),
        )
    conn.commit()
    conn.close()
    return path


def test_is_noise_excluded_from_severity_signal(tmp_path: Path) -> None:
    """A noise row whose severity disagrees with the heuristic must NOT count (ADR-0022)."""
    # 10 non-noise rows that AGREE with the stub classifier (no disagreement) ...
    findings = [
        {"severity": "low", "category": "testing", "summary": f"agree {i}"} for i in range(10)
    ]
    # ... plus 5 NOISE rows whose recorded 'critical' disagrees with the stub's 'low'.
    findings += [
        {"severity": "critical", "category": "testing", "summary": f"noise {i}", "is_noise": 1}
        for i in range(5)
    ]
    db = _make_db(tmp_path / "e.db", findings, [])
    conn = sqlite3.connect(str(db))
    proposals = audit_calibration._severity_marker_disagreement(conn, lambda _s: "low")
    conn.close()
    # Noise rows excluded → all surviving rows agree → no disagreement proposal.
    assert proposals == []


def test_severity_disagreement_triggers_on_non_noise(tmp_path: Path) -> None:
    """Genuine non-noise disagreement above threshold produces a classifier-code proposal."""
    findings = [
        {"severity": "high", "category": "testing", "summary": f"row {i}"} for i in range(10)
    ]
    db = _make_db(tmp_path / "e.db", findings, [])
    conn = sqlite3.connect(str(db))
    proposals = audit_calibration._severity_marker_disagreement(conn, lambda _s: "low")
    conn.close()
    assert len(proposals) == 1
    assert proposals[0].kind == "classifier-code"
    assert proposals[0].signal == "severity-heuristic-disagreement"


def test_category_noise_rate_signal(tmp_path: Path) -> None:
    """A category over the noise-rate threshold yields a proposal carrying noise samples."""
    findings = [
        {"severity": "medium", "category": "testing", "summary": f"real {i}"} for i in range(4)
    ]
    findings += [
        {"severity": "medium", "category": "testing", "summary": f"## Verdict {i}", "is_noise": 1}
        for i in range(6)
    ]
    db = _make_db(tmp_path / "e.db", findings, [])
    result = audit_calibration.audit_calibration(db, write=False)
    noise = [p for p in result.proposals if p.signal == "category-noise-rate"]
    assert len(noise) == 1
    assert noise[0].kind == "classifier-code"
    assert any("## Verdict" in e for e in noise[0].evidence)


def test_calibration_drift_is_single_low_confidence_proposal(tmp_path: Path) -> None:
    """Many drifting agents collapse into ONE low-confidence aggregate proposal."""
    ae = [{"agent": f"a{i}", "cal": 0.5} for i in range(3) for _ in range(8)]
    db = _make_db(tmp_path / "e.db", [], ae)
    result = audit_calibration.audit_calibration(db, write=False)
    drift = [p for p in result.proposals if p.signal == "agent-calibration-drift"]
    assert len(drift) == 1
    assert drift[0].low_confidence is True
    assert drift[0].kind == "skill-rubric"


def test_healthy_db_yields_no_proposals(tmp_path: Path) -> None:
    """Well-calibrated, low-noise, agreeing data produces no proposals."""
    # Plain summaries with no severity keywords classify to the heuristic default 'medium',
    # so recording 'medium' makes heuristic == recorded (genuine agreement, no drift).
    findings = [
        {"severity": "medium", "category": "testing", "summary": f"ok {i}"} for i in range(10)
    ]
    ae = [{"agent": "qa", "cal": 0.05} for _ in range(8)]
    db = _make_db(tmp_path / "e.db", findings, ae)
    result = audit_calibration.audit_calibration(db, write=False)
    assert result.proposals == []


def test_generic_error_on_corrupt_db(tmp_path: Path) -> None:
    """A non-sqlite file surfaces only a generic message — never a raw DB error string."""
    bad = tmp_path / "corrupt.db"
    bad.write_bytes(b"this is not a database" * 50)
    result = audit_calibration.audit_calibration(bad, write=False)
    assert result.proposals == []
    # The note must be EXACTLY "...database error (<TypeName>)." — type name only, no raw
    # message text after the closing paren (covers any sqlite3.Error subclass, not one string).
    assert any(re.search(r"database error \([A-Za-z]+\)\.$", n) for n in result.notes)
    assert not any("file is not a database" in n for n in result.notes)


def test_missing_db_is_noop(tmp_path: Path) -> None:
    """An absent DB is a clean no-op with an informative note, not an error."""
    result = audit_calibration.audit_calibration(tmp_path / "nope.db", write=False)
    assert result.proposals == []
    assert any("not found" in n for n in result.notes)


def test_finding_text_is_display_only_not_a_sink(tmp_path: Path) -> None:
    """Shell metacharacters in finding text appear verbatim in the report (no execution)."""
    payload = "; rm -rf . && echo pwned"
    findings = [
        {"severity": "medium", "category": "testing", "summary": f"real {i}"} for i in range(4)
    ]
    findings += [
        {"severity": "medium", "category": "testing", "summary": payload, "is_noise": 1}
        for _ in range(6)
    ]
    db = _make_db(tmp_path / "e.db", findings, [])
    result = audit_calibration.audit_calibration(db, write=False)
    report = audit_calibration.render_report(result)
    assert payload in report  # literal text, not interpreted


def test_write_only_touches_queue_and_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """write=True writes ONLY the queue artifact + log — never a classifier surface."""
    queue_dir = tmp_path / "queue"
    log_path = tmp_path / "calibration_log.jsonl"
    monkeypatch.setattr(audit_calibration, "QUEUE_DIR", queue_dir)
    monkeypatch.setattr(audit_calibration, "LOG_PATH", log_path)
    ae = [{"agent": f"a{i}", "cal": 0.5} for i in range(2) for _ in range(8)]
    db = _make_db(tmp_path / "e.db", [], ae)
    audit_calibration.audit_calibration(db, write=True)
    written = {p.name for p in queue_dir.iterdir()}
    assert len(written) == 1 and next(iter(written)).startswith("CALIB-")
    assert log_path.exists()
    queue_text = next(queue_dir.iterdir()).read_text(encoding="utf-8")
    assert "status: pending" in queue_text
    assert "not an instruction file" in queue_text


def test_queue_is_append_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two runs at different timestamps produce two files — prior proposals are never lost."""
    queue_dir = tmp_path / "queue"
    monkeypatch.setattr(audit_calibration, "QUEUE_DIR", queue_dir)
    result = audit_calibration.AuditResult()
    result.proposals.append(
        audit_calibration.Proposal(
            surface="x", kind="skill-rubric", signal="s", metric="m", recommendation="r"
        )
    )
    audit_calibration._write_queue(result, "20260613-000001")
    audit_calibration._write_queue(result, "20260613-000002")
    assert len(list(queue_dir.iterdir())) == 2


def test_is_noise_filter_is_precise_not_blanket(tmp_path: Path) -> None:
    """Guard 1 POSITIVE direction (QA blocking finding): non-noise disagreements are still
    counted when agreeing noise rows sit alongside them. Distinguishes a precise is_noise=0
    filter from an accidental blanket exclusion (which would return [] for the wrong reason).
    """
    # 10 NON-noise rows that disagree (recorded 'high' vs stub heuristic 'low') ...
    findings = [
        {"severity": "high", "category": "testing", "summary": f"dis {i}"} for i in range(10)
    ]
    # ... plus 5 NOISE rows that AGREE (recorded 'low' == stub 'low'); must be excluded.
    findings += [
        {"severity": "low", "category": "testing", "summary": f"agree {i}", "is_noise": 1}
        for i in range(5)
    ]
    db = _make_db(tmp_path / "e.db", findings, [])
    conn = sqlite3.connect(str(db))
    proposals = audit_calibration._severity_marker_disagreement(conn, lambda _s: "low")
    conn.close()
    assert len(proposals) == 1
    # Denominator must be 10 (non-noise only), NOT 15 (would mean noise rows leaked in).
    assert "10/10" in proposals[0].metric


def test_noise_rate_respects_min_sample(tmp_path: Path) -> None:
    """Below MIN_SAMPLE rows, a high noise rate must NOT fire (HAVING boundary)."""
    findings = [
        {"severity": "medium", "category": "testing", "summary": f"n{i}", "is_noise": 1}
        for i in range(5)
    ]
    findings += [
        {"severity": "medium", "category": "testing", "summary": f"r{i}"} for i in range(2)
    ]  # 7 total < MIN_SAMPLE (8)
    db = _make_db(tmp_path / "e.db", findings, [])
    result = audit_calibration.audit_calibration(db, write=False)
    assert not any(p.signal == "category-noise-rate" for p in result.proposals)


def test_calibration_drift_respects_min_sample(tmp_path: Path) -> None:
    """Below MIN_SAMPLE records, an over-threshold agent must NOT fire (HAVING boundary)."""
    ae = [{"agent": "a", "cal": 0.5} for _ in range(7)]  # 7 < MIN_SAMPLE (8)
    db = _make_db(tmp_path / "e.db", [], ae)
    result = audit_calibration.audit_calibration(db, write=False)
    assert not any(p.signal == "agent-calibration-drift" for p in result.proposals)


def test_classifier_unavailable_notes_and_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the classifier cannot load, the severity signal degrades to an explicit note."""
    monkeypatch.setattr(audit_calibration, "_load_classifier", lambda: None)
    findings = [{"severity": "high", "category": "testing", "summary": f"x{i}"} for i in range(10)]
    db = _make_db(tmp_path / "e.db", findings, [])
    result = audit_calibration.audit_calibration(db, write=False)
    assert any("unavailable" in n for n in result.notes)
    assert not any(p.signal == "severity-heuristic-disagreement" for p in result.proposals)


def test_classifier_loads_from_repo() -> None:
    """The single-source severity classifier loads by file path regardless of sys.path."""
    classifier = audit_calibration._load_classifier()
    assert classifier is not None
    assert classifier("a critical security vulnerability") == "critical"
