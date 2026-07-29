"""Tests for the briefing ledger.

The central property under test is that deferring is a recorded outcome, never
a failure state — the ledger has no pass/fail and cannot block anything.
"""

import sqlite3

import pytest

from scripts.briefing import (
    DEPTHS,
    OUTCOMES,
    ledger,
    record,
    record_outcome,
    regret_report,
)
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


class TestOutcomeJoin:
    """The join ADR-0029 needed and originally lacked.

    Without an outcome column a deferral and a later regression are two rows
    that never meet, so the risk weights can never be checked against regret.
    """

    def test_outcome_is_null_until_known(self, db):
        record("src/a.py", "deep", 6, deferred=True, db_path=db)
        assert rows(db)[0]["outcome"] is None

    def test_record_outcome_sets_all_three_fields(self, db):
        record("src/a.py", "deep", 6, deferred=True, db_path=db)
        record_outcome(1, "regressed", ref="REV-123", db_path=db)
        row = rows(db)[0]
        assert row["outcome"] == "regressed"
        assert row["outcome_ref"] == "REV-123"
        assert row["outcome_at"]

    @pytest.mark.parametrize("outcome", OUTCOMES)
    def test_all_outcomes_accepted(self, outcome, db):
        record("src/a.py", "light", 0, db_path=db)
        record_outcome(1, outcome, db_path=db)
        assert rows(db)[0]["outcome"] == outcome

    def test_invalid_outcome_rejected(self, db):
        record("src/a.py", "light", 0, db_path=db)
        with pytest.raises(ValueError, match="outcome must be one of"):
            record_outcome(1, "catastrophe", db_path=db)

    def test_unknown_id_is_reported_not_silent(self, db, capsys):
        record_outcome(999, "clean", db_path=db)
        assert "No briefing with id 999" in capsys.readouterr().out

    def test_regret_report_says_so_when_unanswerable(self, db):
        record("src/a.py", "deep", 6, deferred=True, db_path=db)
        out = regret_report(db_path=db)
        assert "not yet answerable" in out
        assert "1 briefing(s) awaiting" in out

    def test_regret_report_crosses_depth_status_and_outcome(self, db):
        record("src/a.py", "deep", 6, deferred=True, db_path=db)
        record("src/b.py", "standard", 3, db_path=db)
        record_outcome(1, "regressed", db_path=db)
        record_outcome(2, "clean", db_path=db)
        out = regret_report(db_path=db)
        assert "deep" in out and "deferred" in out and "regressed" in out
        assert "standard" in out and "delivered" in out and "clean" in out


class TestFreshCheckout:
    """B4: an unguarded connect left a 0-byte DB that broke create_discussion."""

    def test_record_on_missing_db_self_initializes(self, tmp_path):
        db = tmp_path / "sub" / "evaluation.db"
        record("src/a.py", "light", 0, db_path=db)
        assert db.exists() and db.stat().st_size > 0
        assert rows(db)[0]["scope"] == "src/a.py"

    def test_other_tables_exist_after_self_init(self, tmp_path):
        """The cascade: a stub DB would break every peer script afterwards."""
        db = tmp_path / "evaluation.db"
        record("src/a.py", "light", 0, db_path=db)
        conn = sqlite3.connect(str(db))
        try:
            names = {
                r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
        finally:
            conn.close()
        assert {"discussions", "turns", "findings", "protocol_yield"} <= names
