"""Tests for scripts/close_discussion.py Step 3b (token rollup + clobber guard).

These are regression tests for the ADR-0013 token telemetry pipeline. The
rollup in close_discussion() must NOT overwrite discussion totals that the
JSONL ingester (scripts/ingest_token_usage.py) already wrote.

Strategy: we don't run the full close_discussion() workflow (which expects a
discussion directory with events.jsonl). Instead we exercise the rollup logic
in isolation by replicating its exact SQL against a temp DB. This keeps tests
fast and focused on the contract under test: "skip rollup when no per-turn
token data exists, run rollup when it does."

The SQL fragments here are kept in lockstep with close_discussion.py's
Step 3b — if that step's SQL changes, these tests must be updated too.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from scripts.init_db import init_db


def _run_rollup(db_path: Path, discussion_id: str) -> None:
    """Replicate the Step 3b rollup block from scripts/close_discussion.py.

    Reads the discussion's turns; if ANY turn carries non-NULL token data,
    runs the four UPDATE subqueries that overwrite discussions.total_*.
    Otherwise the totals are left untouched — that is the clobber guard.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    has_turn_tokens = conn.execute(
        """SELECT 1 FROM turns
           WHERE discussion_id = ?
               AND (tokens_in IS NOT NULL OR tokens_out IS NOT NULL
                    OR cache_read_tokens IS NOT NULL OR cache_create_tokens IS NOT NULL)
           LIMIT 1""",
        (discussion_id,),
    ).fetchone()
    if has_turn_tokens:
        conn.execute(
            """UPDATE discussions
               SET total_tokens_in = (
                       SELECT SUM(tokens_in) FROM turns
                       WHERE discussion_id = ? AND tokens_in IS NOT NULL
                   ),
                   total_tokens_out = (
                       SELECT SUM(tokens_out) FROM turns
                       WHERE discussion_id = ? AND tokens_out IS NOT NULL
                   ),
                   total_cache_tokens = (
                       SELECT SUM(
                           COALESCE(cache_read_tokens, 0) + COALESCE(cache_create_tokens, 0)
                       )
                       FROM turns
                       WHERE discussion_id = ?
                           AND (cache_read_tokens IS NOT NULL OR cache_create_tokens IS NOT NULL)
                   )
               WHERE discussion_id = ?""",
            (discussion_id, discussion_id, discussion_id, discussion_id),
        )
        conn.commit()
    conn.close()


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """Create a temp DB with the full framework schema."""
    path = tmp_path / "rollup.db"
    init_db(path)
    return path


def _insert_discussion(
    db_path: Path,
    discussion_id: str,
    *,
    total_in: int | None,
    total_out: int | None,
    total_cache: int | None,
) -> None:
    """Insert a closed discussion with pre-set total_* values (as if ingester wrote them)."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        "INSERT INTO discussions "
        "(discussion_id, created_at, closed_at, risk_level, collaboration_mode, "
        "status, agent_count, total_tokens_in, total_tokens_out, total_cache_tokens) "
        "VALUES (?, '2026-01-01T00:00:00+00:00', '2026-01-01T23:59:59+00:00', "
        "'low', 'ensemble', 'closed', 0, ?, ?, ?)",
        (discussion_id, total_in, total_out, total_cache),
    )
    conn.commit()
    conn.close()


def _insert_turn(
    db_path: Path,
    discussion_id: str,
    turn_id: int,
    *,
    tokens_in: int | None,
    tokens_out: int | None,
    cache_read: int | None,
    cache_create: int | None,
) -> None:
    """Insert one turn with the given token columns (any/all may be NULL)."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        "INSERT INTO turns "
        "(discussion_id, turn_id, agent, intent, timestamp, confidence, content_hash, "
        "tokens_in, tokens_out, cache_read_tokens, cache_create_tokens) "
        "VALUES (?, ?, 'qa-specialist', 'critique', '2026-01-01T10:00:00+00:00', "
        "0.8, 'hash', ?, ?, ?, ?)",
        (discussion_id, turn_id, tokens_in, tokens_out, cache_read, cache_create),
    )
    conn.commit()
    conn.close()


def _read_totals(db_path: Path, discussion_id: str) -> tuple:
    """Read back (total_tokens_in, total_tokens_out, total_cache_tokens)."""
    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT total_tokens_in, total_tokens_out, total_cache_tokens "
        "FROM discussions WHERE discussion_id = ?",
        (discussion_id,),
    ).fetchone()
    conn.close()
    return row


@pytest.mark.regression
class TestClobberGuard:
    """Regression: rollup must NOT overwrite ingester-written totals when turns are NULL.

    Bug class: if Step 3b unconditionally ran the rollup UPDATEs, every closed
    discussion would have its totals reset to NULL whenever no turn carried
    token data — silently destroying the JSONL ingester's work. The guard
    (Step 3b's ``has_turn_tokens`` check) prevents this.
    """

    def test_no_turn_tokens_preserves_totals(self, db_path: Path) -> None:
        """All-NULL turn tokens → discussion totals unchanged (clobber-guard fires)."""
        _insert_discussion(db_path, "DISC-PRESERVE", total_in=999, total_out=888, total_cache=777)
        # Three turns, all with NULL token columns.
        for tid in (1, 2, 3):
            _insert_turn(
                db_path,
                "DISC-PRESERVE",
                tid,
                tokens_in=None,
                tokens_out=None,
                cache_read=None,
                cache_create=None,
            )

        _run_rollup(db_path, "DISC-PRESERVE")

        # CRITICAL: the ingester-written values must survive.
        assert _read_totals(db_path, "DISC-PRESERVE") == (999, 888, 777)


class TestRollupWhenTurnDataExists:
    """Verify the rollup actually runs when at least one turn has token data."""

    def test_rollup_overwrites_with_turn_sum(self, db_path: Path) -> None:
        """At least one turn has token data → rollup writes the SUM(turns.*) values."""
        # Pre-populate with stale "ingester-written" totals — rollup should overwrite
        # because turn data is present.
        _insert_discussion(db_path, "DISC-ROLLUP", total_in=999, total_out=999, total_cache=999)
        _insert_turn(
            db_path,
            "DISC-ROLLUP",
            1,
            tokens_in=100,
            tokens_out=200,
            cache_read=None,
            cache_create=None,
        )

        _run_rollup(db_path, "DISC-ROLLUP")

        in_, out_, cache_ = _read_totals(db_path, "DISC-ROLLUP")
        assert in_ == 100
        assert out_ == 200

    def test_rollup_preserves_null_for_unrolled_columns(self, db_path: Path) -> None:
        """A turn with tokens_in only → in is summed; out and cache stay NULL.

        Confirms the honest-NULL contract: if no turn carries data for a
        column, the rollup's outer ``WHERE ... IS NOT NULL`` subquery returns
        an empty set and SUM() yields NULL — not 0.
        """
        _insert_discussion(db_path, "DISC-NULL", total_in=None, total_out=None, total_cache=None)
        _insert_turn(
            db_path,
            "DISC-NULL",
            1,
            tokens_in=100,
            tokens_out=None,
            cache_read=None,
            cache_create=None,
        )

        _run_rollup(db_path, "DISC-NULL")

        in_, out_, cache_ = _read_totals(db_path, "DISC-NULL")
        assert in_ == 100
        # Honest NULL — not zero — for the columns no turn populated.
        assert out_ is None
        assert cache_ is None
