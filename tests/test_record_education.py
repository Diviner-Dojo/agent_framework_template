"""Tests for scripts/record_education.py."""

import sqlite3

import pytest

from scripts.init_db import init_db
from scripts.record_education import record_education


@pytest.fixture()
def db_path(tmp_path):
    """Create a temporary database with schema."""
    path = tmp_path / "test.db"
    init_db(path)
    # Create a discussion for FK reference
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        "INSERT INTO discussions (discussion_id, created_at, risk_level, "
        "collaboration_mode, status, agent_count) "
        "VALUES ('DISC-TEST', '2026-01-01T00:00:00', 'low', 'ensemble', 'open', 0)"
    )
    conn.commit()
    conn.close()
    return path


class TestRecordEducation:
    """Tests for the record_education function."""

    def test_happy_path(self, db_path):
        """Record a valid education result."""
        record_education("QUIZ-001", "DISC-TEST", "understand", "walkthrough", 0.85, True, db_path)
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT * FROM education_results").fetchone()
        conn.close()
        assert row is not None
        assert row[1] == "QUIZ-001"  # session_id
        assert row[3] == "understand"  # bloom_level
        assert row[5] == 0.85  # score
        assert row[6] == 1  # passed (True -> 1)

    def test_score_boundary_zero(self, db_path):
        """Score of 0.0 is valid."""
        record_education("QUIZ-002", "DISC-TEST", "remember", "recall", 0.0, False, db_path)
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT score FROM education_results").fetchone()
        conn.close()
        assert row[0] == 0.0

    def test_score_boundary_one(self, db_path):
        """Score of 1.0 is valid."""
        record_education("QUIZ-003", "DISC-TEST", "create", "explain-back", 1.0, True, db_path)
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT score FROM education_results").fetchone()
        conn.close()
        assert row[0] == 1.0

    def test_score_out_of_range_high(self, db_path):
        """Score > 1.0 violates CHECK constraint."""
        with pytest.raises(sqlite3.IntegrityError):
            record_education(
                "QUIZ-004", "DISC-TEST", "apply", "debug-scenario", 1.01, True, db_path
            )

    def test_score_out_of_range_negative(self, db_path):
        """Negative score violates CHECK constraint."""
        with pytest.raises(sqlite3.IntegrityError):
            record_education(
                "QUIZ-005", "DISC-TEST", "analyze", "change-impact", -0.01, False, db_path
            )

    def test_passed_false(self, db_path):
        """Passed=False records correctly."""
        record_education(
            "QUIZ-006", "DISC-TEST", "evaluate", "debug-scenario", 0.5, False, db_path
        )
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT passed FROM education_results").fetchone()
        conn.close()
        assert row[0] == 0  # False -> 0

    def test_multiple_records(self, db_path):
        """Multiple records can be inserted."""
        for i in range(3):
            record_education(
                f"QUIZ-{i}",
                "DISC-TEST",
                "understand",
                "walkthrough",
                0.7 + i * 0.1,
                i > 0,
                db_path,
            )
        conn = sqlite3.connect(str(db_path))
        count = conn.execute("SELECT COUNT(*) FROM education_results").fetchone()[0]
        conn.close()
        assert count == 3
