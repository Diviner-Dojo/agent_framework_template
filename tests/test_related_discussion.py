"""Tests for the related_discussion_id feature in init_db and create_discussion."""

import sqlite3

from scripts.init_db import init_db


class TestRelatedDiscussionMigration:
    """Tests for the related_discussion_id column migration."""

    def test_fresh_db_has_column(self, tmp_path):
        """A fresh database has the related_discussion_id column."""
        db_path = tmp_path / "fresh.db"
        init_db(db_path)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("PRAGMA table_info(discussions)")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()
        assert "related_discussion_id" in columns

    def test_existing_db_without_column_gets_migration(self, tmp_path):
        """An existing DB without the column gets it via migration."""
        db_path = tmp_path / "old.db"
        # Create a minimal DB without the column
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE discussions (
                discussion_id TEXT PRIMARY KEY,
                created_at DATETIME NOT NULL,
                risk_level TEXT NOT NULL CHECK(risk_level IN ('low','medium','high','critical')),
                collaboration_mode TEXT NOT NULL CHECK(collaboration_mode IN (
                    'ensemble','yes-and','structured-dialogue','dialectic','adversarial'
                )),
                exploration_intensity TEXT NOT NULL DEFAULT 'medium',
                status TEXT NOT NULL DEFAULT 'open',
                linked_decision TEXT,
                linked_pr TEXT,
                agent_count INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()

        # Run init_db which should add the column via migration
        init_db(db_path)

        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("PRAGMA table_info(discussions)")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()
        assert "related_discussion_id" in columns

    def test_existing_db_with_column_no_error(self, tmp_path):
        """Running init_db twice doesn't error (migration is idempotent)."""
        db_path = tmp_path / "twice.db"
        init_db(db_path)
        init_db(db_path)  # Should not raise

        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("PRAGMA table_info(discussions)")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()
        assert "related_discussion_id" in columns

    def test_related_discussion_id_can_be_inserted(self, tmp_path):
        """A discussion with related_discussion_id can be inserted."""
        db_path = tmp_path / "insert.db"
        init_db(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO discussions (discussion_id, created_at, risk_level, "
            "collaboration_mode, status, agent_count, related_discussion_id) "
            "VALUES ('DISC-A', '2026-01-01', 'low', 'ensemble', 'open', 0, 'DISC-B')"
        )
        conn.commit()
        row = conn.execute(
            "SELECT related_discussion_id FROM discussions WHERE discussion_id='DISC-A'"
        ).fetchone()
        conn.close()
        assert row[0] == "DISC-B"

    def test_related_discussion_id_nullable(self, tmp_path):
        """related_discussion_id can be NULL."""
        db_path = tmp_path / "null.db"
        init_db(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO discussions (discussion_id, created_at, risk_level, "
            "collaboration_mode, status, agent_count) "
            "VALUES ('DISC-C', '2026-01-01', 'low', 'ensemble', 'open', 0)"
        )
        conn.commit()
        row = conn.execute(
            "SELECT related_discussion_id FROM discussions WHERE discussion_id='DISC-C'"
        ).fetchone()
        conn.close()
        assert row[0] is None
