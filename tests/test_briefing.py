"""Tests for the briefing ledger.

The central property under test is that deferring is a recorded outcome, never
a failure state — the ledger has no pass/fail and cannot block anything.
"""

import sqlite3

import pytest

from scripts.briefing import DEPTHS, ledger, record
from scripts.init_db import init_db


@pytest.fixture
def db(tmp_path):
    """A freshly initialized metrics database."""
    path = tmp_path / "evaluation.db"
    init_db(path, quiet=True)
    return path


def rows(db):
    """Return all briefing rows as dicts."""
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM briefings")]
    finally:
        conn.close()


class TestRecord:
    def test_delivered_briefing_is_recorded(self, db):
        record(
            "src/auth.py", "standard", 3, concept="Tokens rotate on privilege change", db_path=db
        )
        (row,) = rows(db)
        assert row["status"] == "delivered"
        assert row["scope"] == "src/auth.py"
        assert row["depth"] == "standard"
        assert row["risk_score"] == 3
        assert row["concept"] == "Tokens rotate on privilege change"

    def test_deferred_briefing_is_recorded_not_rejected(self, db):
        record("src/auth.py", "deep", 6, deferred=True, note="shipping a demo", db_path=db)
        (row,) = rows(db)
        assert row["status"] == "deferred"
        assert row["note"] == "shipping a demo"

    def test_deferral_needs_no_justification(self, db):
        record("src/auth.py", "deep", 6, deferred=True, db_path=db)
        assert rows(db)[0]["note"] is None

    @pytest.mark.parametrize("depth", DEPTHS)
    def test_all_depths_accepted(self, depth, db):
        record("scope", depth, 1, db_path=db)
        assert rows(db)[0]["depth"] == depth

    def test_invalid_depth_rejected(self, db):
        with pytest.raises(ValueError, match="depth must be one of"):
            record("scope", "exhaustive", 1, db_path=db)

    def test_timestamp_is_recorded(self, db):
        record("scope", "light", 0, db_path=db)
        assert rows(db)[0]["timestamp"]

    def test_no_score_or_pass_fail_column_exists(self, db):
        """The ledger must not be able to grade the developer."""
        conn = sqlite3.connect(str(db))
        try:
            columns = {c[1] for c in conn.execute("PRAGMA table_info(briefings)")}
        finally:
            conn.close()
        assert "score" not in columns
        assert "passed" not in columns


class TestLedger:
    def test_empty_ledger(self, db):
        output = ledger(db_path=db)
        assert "0 delivered, 0 deferred" in output
        assert "nothing recorded yet" in output

    def test_counts_both_statuses(self, db):
        record("a", "light", 0, db_path=db)
        record("b", "deep", 6, deferred=True, db_path=db)
        record("c", "standard", 3, db_path=db)
        output = ledger(db_path=db)
        assert "2 delivered, 1 deferred" in output

    def test_deferred_message_is_not_punitive(self, db):
        record("a", "deep", 6, deferred=True, db_path=db)
        output = ledger(db_path=db)
        assert "No rush." in output

    def test_no_deferred_message_when_none_deferred(self, db):
        record("a", "light", 0, db_path=db)
        assert "No rush." not in ledger(db_path=db)

    def test_concept_shown_in_ledger(self, db):
        record("src/a.py", "standard", 3, concept="The queue is at-least-once", db_path=db)
        assert "The queue is at-least-once" in ledger(db_path=db)

    def test_limit_is_respected(self, db):
        for i in range(5):
            record(f"scope-{i}", "light", 0, db_path=db)
        output = ledger(db_path=db, limit=2)
        assert output.count("[light]") == 2
