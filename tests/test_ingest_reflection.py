"""Tests for scripts/ingest_reflection.py."""

import sqlite3

import pytest

from scripts.ingest_reflection import ingest_reflection, parse_reflection
from scripts.init_db import init_db


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


VALID_REFLECTION = """\
---
reflection_id: REFL-20260101-000000-qa
discussion_id: DISC-TEST
agent: qa-specialist
timestamp: 2026-01-01T00:00:00
---

## What I Missed
I should have checked the edge case for empty inputs.

## Candidate Improvement Rule
Always verify boundary conditions before approving.

## Confidence Calibration
Original: 0.8, Revised: 0.7, Delta: -0.1
"""


class TestParseReflection:
    """Tests for the parse_reflection function."""

    def test_valid_reflection(self, tmp_path):
        """Parse a well-formed reflection file."""
        f = tmp_path / "refl.md"
        f.write_text(VALID_REFLECTION, encoding="utf-8")
        data = parse_reflection(f)
        assert data["reflection_id"] == "REFL-20260101-000000-qa"
        assert data["discussion_id"] == "DISC-TEST"
        assert data["agent"] == "qa-specialist"
        assert "edge case" in data["missed_signal"]
        assert "boundary conditions" in data["improvement_rule"]
        assert data["confidence_delta"] == -0.1

    def test_missing_frontmatter(self, tmp_path):
        """File without frontmatter raises ValueError."""
        f = tmp_path / "bad.md"
        f.write_text("No frontmatter here\n## Section\nContent\n", encoding="utf-8")
        with pytest.raises(ValueError, match="No YAML frontmatter"):
            parse_reflection(f)

    def test_missing_delta(self, tmp_path):
        """Reflection without Delta line returns None for confidence_delta."""
        content = """\
---
reflection_id: REFL-002
discussion_id: DISC-TEST
agent: arch
timestamp: 2026-01-01
---

## What I Missed
Nothing major.

## Candidate Improvement Rule
None needed.

## Confidence Calibration
I was appropriately confident.
"""
        f = tmp_path / "refl2.md"
        f.write_text(content, encoding="utf-8")
        data = parse_reflection(f)
        assert data["confidence_delta"] is None

    def test_positive_delta(self, tmp_path):
        """Positive delta value is parsed correctly."""
        content = """\
---
reflection_id: REFL-003
discussion_id: DISC-TEST
agent: sec
timestamp: 2026-01-01
---

## What I Missed
Minor issue.

## Confidence Calibration
Original: 0.7, Revised: 0.9, Delta: +0.2
"""
        f = tmp_path / "refl3.md"
        f.write_text(content, encoding="utf-8")
        data = parse_reflection(f)
        assert data["confidence_delta"] == 0.2

    def test_frontmatter_with_colons_in_value(self, tmp_path):
        """Frontmatter values containing colons are parsed correctly."""
        content = """\
---
reflection_id: REFL-20260323-182242-qa
discussion_id: DISC-20260323-182242-v31-foo
agent: qa-specialist
timestamp: 2026-03-23T18:22:42
---

## What I Missed
Nothing.
"""
        f = tmp_path / "refl4.md"
        f.write_text(content, encoding="utf-8")
        data = parse_reflection(f)
        assert data["discussion_id"] == "DISC-20260323-182242-v31-foo"
        assert data["timestamp"] == "2026-03-23T18:22:42"


class TestIngestReflection:
    """Tests for the ingest_reflection function."""

    def test_happy_path(self, tmp_path, db_path):
        """Ingest a valid reflection into SQLite."""
        f = tmp_path / "refl.md"
        f.write_text(VALID_REFLECTION, encoding="utf-8")
        ingest_reflection(f, db_path)

        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT * FROM reflections").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "REFL-20260101-000000-qa"  # reflection_id
        assert row[2] == "qa-specialist"  # agent

    def test_duplicate_reflection_id_ignored(self, tmp_path, db_path):
        """Duplicate reflection_id is silently ignored (INSERT OR IGNORE)."""
        f = tmp_path / "refl.md"
        f.write_text(VALID_REFLECTION, encoding="utf-8")
        ingest_reflection(f, db_path)
        ingest_reflection(f, db_path)  # Second insert

        conn = sqlite3.connect(str(db_path))
        count = conn.execute("SELECT COUNT(*) FROM reflections").fetchone()[0]
        conn.close()
        assert count == 1

    def test_confidence_delta_stored(self, tmp_path, db_path):
        """Confidence delta is stored correctly."""
        f = tmp_path / "refl.md"
        f.write_text(VALID_REFLECTION, encoding="utf-8")
        ingest_reflection(f, db_path)

        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT confidence_delta FROM reflections").fetchone()
        conn.close()
        assert row[0] == -0.1
