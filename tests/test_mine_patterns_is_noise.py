"""Tests for AC6: mine_patterns excludes is_noise=1 findings on both query branches.

Both the discussion_id path and the --all (LEFT JOIN) path must filter is_noise=0.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

TEMPLATE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(TEMPLATE_ROOT))
# scripts/ must be on path for pipeline_utils (a sibling-script import in mine_patterns).
sys.path.insert(0, str(TEMPLATE_ROOT / "scripts"))

from scripts import mine_patterns as mp_module  # noqa: E402
from scripts.init_db import init_db  # noqa: E402
from scripts.mine_patterns import mine_patterns  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "eval.db"
    init_db(db_path, quiet=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO discussions "
        "(discussion_id, created_at, risk_level, collaboration_mode) "
        "VALUES ('DISC-mine-test', '2026-06-12T00:00:00+00:00', 'medium', 'ensemble')"
    )
    conn.commit()
    conn.close()
    return db_path


def _insert_finding(db_path: Path, summary: str, is_noise: int = 0) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """INSERT INTO findings
           (discussion_id, turn_id, agent, severity, category, summary, raw_excerpt,
            created_at, is_noise)
           VALUES ('DISC-mine-test', 1, 'qa-specialist', 'medium', 'testing',
                   ?, ?, '2026-06-12T00:00:00+00:00', ?)""",
        (summary, summary, is_noise),
    )
    conn.commit()
    conn.close()


def _pattern_sighting_count(db_path: Path) -> int:
    conn = sqlite3.connect(str(db_path))
    n = conn.execute("SELECT COUNT(*) FROM pattern_sightings").fetchone()[0]
    conn.close()
    return n


# ---------------------------------------------------------------------------
# AC6 tests
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_mine_patterns_discussion_id_path_excludes_noise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC6: discussion_id query branch produces no sighting from an is_noise=1 finding."""
    db_path = _setup_db(tmp_path)
    monkeypatch.setattr(mp_module, "DB_PATH", db_path)

    _insert_finding(db_path, "## Findings", is_noise=1)  # noise — must be excluded

    result = mine_patterns("DISC-mine-test")

    assert result == 0
    assert _pattern_sighting_count(db_path) == 0


@pytest.mark.regression
def test_mine_patterns_all_path_excludes_noise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC6: --all (LEFT JOIN) query branch produces no sighting from an is_noise=1 finding."""
    db_path = _setup_db(tmp_path)
    monkeypatch.setattr(mp_module, "DB_PATH", db_path)

    _insert_finding(db_path, "Security Review: 5 findings", is_noise=1)  # noise

    result = mine_patterns(None)  # None → --all path

    assert result == 0
    assert _pattern_sighting_count(db_path) == 0


def test_mine_patterns_discussion_id_path_includes_non_noise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC6: non-noise finding on discussion_id path does produce a pattern sighting."""
    db_path = _setup_db(tmp_path)
    monkeypatch.setattr(mp_module, "DB_PATH", db_path)

    _insert_finding(db_path, "Missing test coverage for the empty-events branch", is_noise=0)

    result = mine_patterns("DISC-mine-test")

    assert result >= 1
    assert _pattern_sighting_count(db_path) >= 1


def test_mine_patterns_all_path_includes_non_noise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC6: non-noise finding on --all path does produce a pattern sighting."""
    db_path = _setup_db(tmp_path)
    monkeypatch.setattr(mp_module, "DB_PATH", db_path)

    _insert_finding(db_path, "Race condition in the connection pool", is_noise=0)

    result = mine_patterns(None)

    assert result >= 1
    assert _pattern_sighting_count(db_path) >= 1
