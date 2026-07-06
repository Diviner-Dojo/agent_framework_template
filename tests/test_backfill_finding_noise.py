"""Tests for scripts/backfill_finding_noise.py (AC4, AC5).

AC4: init_db creates findings.is_noise; migration is idempotent (no dup-column error).
AC5: backfill flags scaffold rows is_noise=1, leaves row count unchanged (no deletes),
     reduces spurious critical rows, and is idempotent (second run = zero DB writes).
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

TEMPLATE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(TEMPLATE_ROOT))
# scripts/ must be on path for backfill_finding_noise's cross-import of extract_findings.
sys.path.insert(0, str(TEMPLATE_ROOT / "scripts"))

from scripts import backfill_finding_noise as bf_module  # noqa: E402
from scripts.backfill_finding_noise import run_backfill  # noqa: E402
from scripts.init_db import init_db  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_findings(db_path: Path, rows: list[dict]) -> None:
    """Insert findings rows into a fresh DB (discussion seed included)."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO discussions "
        "(discussion_id, created_at, risk_level, collaboration_mode) "
        "VALUES ('DISC-seed', '2026-06-12T00:00:00+00:00', 'medium', 'ensemble')"
    )
    for r in rows:
        conn.execute(
            """INSERT INTO findings
               (discussion_id, turn_id, agent, severity, category,
                summary, raw_excerpt, created_at, is_noise)
               VALUES (?, ?, ?, ?, ?, ?, ?, '2026-06-12T00:00:00+00:00', 0)""",
            (
                "DISC-seed",
                r.get("turn_id", 1),
                r.get("agent", "qa-specialist"),
                r.get("severity", "medium"),
                r.get("category", "general"),
                r["summary"],
                r.get("raw_excerpt", r["summary"]),
            ),
        )
    conn.commit()
    conn.close()


def _count_rows(db_path: Path) -> int:
    conn = sqlite3.connect(str(db_path))
    n = conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
    conn.close()
    return n


def _noise_count(db_path: Path) -> int:
    conn = sqlite3.connect(str(db_path))
    n = conn.execute("SELECT COUNT(*) FROM findings WHERE is_noise = 1").fetchone()[0]
    conn.close()
    return n


# ---------------------------------------------------------------------------
# AC4: init_db creates is_noise; migration idempotent
# ---------------------------------------------------------------------------


def test_init_db_creates_is_noise_column(tmp_path: Path) -> None:
    """AC4: init_db creates findings.is_noise column."""
    db_path = tmp_path / "eval.db"
    init_db(db_path, quiet=True)
    conn = sqlite3.connect(str(db_path))
    cols = [row[1] for row in conn.execute("PRAGMA table_info(findings)").fetchall()]
    conn.close()
    assert "is_noise" in cols


def test_init_db_is_noise_column_idempotent(tmp_path: Path) -> None:
    """AC4: running init_db twice does not raise (no dup-column error)."""
    db_path = tmp_path / "eval.db"
    init_db(db_path, quiet=True)
    init_db(db_path, quiet=True)  # Must not raise


def test_pre_migration_db_gains_is_noise_via_backfill(tmp_path: Path) -> None:
    """AC4: a DB without is_noise gets the column added by run_backfill."""
    db_path = tmp_path / "eval.db"
    init_db(db_path, quiet=True)
    # Simulate a pre-migration DB by dropping is_noise (recreate without it).
    conn = sqlite3.connect(str(db_path))
    conn.execute("ALTER TABLE findings RENAME TO findings_old")
    conn.execute(
        """CREATE TABLE findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discussion_id TEXT NOT NULL,
            turn_id INTEGER NOT NULL,
            agent TEXT NOT NULL,
            severity TEXT NOT NULL,
            category TEXT NOT NULL,
            summary TEXT NOT NULL,
            raw_excerpt TEXT,
            resolved BOOLEAN NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        "INSERT INTO findings SELECT "
        "id,discussion_id,turn_id,agent,severity,category,"
        "summary,raw_excerpt,resolved,created_at FROM findings_old"
    )
    conn.execute("DROP TABLE findings_old")
    conn.commit()
    conn.close()

    run_backfill(db_path)  # Must not raise; adds the column

    conn = sqlite3.connect(str(db_path))
    cols = [row[1] for row in conn.execute("PRAGMA table_info(findings)").fetchall()]
    conn.close()
    assert "is_noise" in cols


# ---------------------------------------------------------------------------
# AC5: backfill correctness, no-delete, idempotency
# ---------------------------------------------------------------------------

_SCAFFOLD_ROWS = [
    {"summary": "## Findings", "severity": "critical"},  # scaffold — should be flagged
    {"summary": "Security Review: 5 findings", "severity": "critical"},  # scaffold
    {"summary": "8 findings (1 HIGH blocking, 7 advisory)", "severity": "high"},  # scaffold
]
_SUBSTANTIVE_ROWS = [
    {"summary": "Missing validation on the discussion_id parameter", "severity": "critical"},
    {
        "summary": "Race condition in the connection pool under concurrent writes",
        "severity": "info",
    },
]


@pytest.mark.regression
def test_backfill_flags_scaffold_rows_as_noise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC5: scaffold rows get is_noise=1; substantive rows keep is_noise=0."""
    db_path = tmp_path / "eval.db"
    init_db(db_path, quiet=True)
    monkeypatch.setattr(bf_module, "DB_PATH", db_path)
    all_rows = _SCAFFOLD_ROWS + _SUBSTANTIVE_ROWS
    _seed_findings(db_path, all_rows)

    run_backfill(db_path)

    assert _noise_count(db_path) == len(_SCAFFOLD_ROWS)


def test_backfill_does_not_delete_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC5: backfill never deletes rows — total count unchanged."""
    db_path = tmp_path / "eval.db"
    init_db(db_path, quiet=True)
    monkeypatch.setattr(bf_module, "DB_PATH", db_path)
    all_rows = _SCAFFOLD_ROWS + _SUBSTANTIVE_ROWS
    _seed_findings(db_path, all_rows)
    before = _count_rows(db_path)

    run_backfill(db_path)

    assert _count_rows(db_path) == before


def test_backfill_recalibrates_severity_for_non_noise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC5: non-noise row 'race condition' is recalibrated from info → high."""
    db_path = tmp_path / "eval.db"
    init_db(db_path, quiet=True)
    monkeypatch.setattr(bf_module, "DB_PATH", db_path)
    _seed_findings(
        db_path, [{"summary": "Race condition in the connection pool", "severity": "info"}]
    )

    run_backfill(db_path)

    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT severity, is_noise FROM findings LIMIT 1").fetchone()
    conn.close()
    assert row[1] == 0  # not noise
    assert row[0] == "high"  # recalibrated


def test_backfill_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC5: second run issues zero DB writes."""
    db_path = tmp_path / "eval.db"
    init_db(db_path, quiet=True)
    monkeypatch.setattr(bf_module, "DB_PATH", db_path)
    _seed_findings(db_path, _SCAFFOLD_ROWS + _SUBSTANTIVE_ROWS)

    run_backfill(db_path)  # First run
    result = run_backfill(db_path)  # Second run

    assert result["db_writes"] == 0, (
        f"Second run wrote {result['db_writes']} rows — not idempotent"
    )


def test_backfill_dry_run_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC5: --dry-run prints but makes no DB writes."""
    db_path = tmp_path / "eval.db"
    init_db(db_path, quiet=True)
    monkeypatch.setattr(bf_module, "DB_PATH", db_path)
    _seed_findings(db_path, _SCAFFOLD_ROWS)

    result = run_backfill(db_path, dry_run=True)

    assert result["db_writes"] == 0
    assert _noise_count(db_path) == 0  # DB unchanged
    # qa F3 fold (DISC-20260612-144008): the dry-run histogram must still be
    # computed — a bug that zeroed the counts while writing nothing would pass
    # the two asserts above.
    assert result["noise_flagged"] == len(_SCAFFOLD_ROWS)
    assert result["total"] == len(_SCAFFOLD_ROWS)


def test_backfill_missing_db_returns_zero_dict(tmp_path: Path) -> None:
    """qa F4 fold (DISC-20260612-144008): missing DB short-circuits to zeros, no raise."""
    result = run_backfill(tmp_path / "nope.db")
    assert result == {"total": 0, "noise_flagged": 0, "severity_changed": 0, "db_writes": 0}
