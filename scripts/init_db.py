"""Initialize the Layer 2 SQLite relational index.

Creates metrics/evaluation.db with all framework tables.
Safe to run multiple times — uses CREATE TABLE IF NOT EXISTS.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "metrics" / "evaluation.db"


def init_db(db_path: Path = DB_PATH) -> None:
    """Create all framework tables in the SQLite database."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS discussions (
            discussion_id   TEXT PRIMARY KEY,
            created_at      DATETIME NOT NULL,
            closed_at       DATETIME,
            risk_level      TEXT NOT NULL CHECK(risk_level IN ('low', 'medium', 'high', 'critical')),
            collaboration_mode TEXT NOT NULL CHECK(collaboration_mode IN (
                'ensemble', 'yes-and', 'structured-dialogue', 'dialectic', 'adversarial'
            )),
            exploration_intensity TEXT NOT NULL DEFAULT 'medium'
                CHECK(exploration_intensity IN ('low', 'medium', 'high')),
            status          TEXT NOT NULL DEFAULT 'open'
                CHECK(status IN ('open', 'closed', 'reopened')),
            linked_decision TEXT,
            linked_pr       TEXT,
            agent_count     INTEGER NOT NULL DEFAULT 0,
            command_type    TEXT,
            duration_minutes REAL
        );

        CREATE TABLE IF NOT EXISTS turns (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            discussion_id   TEXT NOT NULL REFERENCES discussions(discussion_id),
            turn_id         INTEGER NOT NULL,
            agent           TEXT NOT NULL,
            reply_to        INTEGER,
            intent          TEXT NOT NULL CHECK(intent IN (
                'proposal', 'critique', 'question', 'evidence',
                'synthesis', 'decision', 'reflection'
            )),
            timestamp       DATETIME NOT NULL,
            confidence      REAL NOT NULL CHECK(confidence >= 0.0 AND confidence <= 1.0),
            content_hash    TEXT NOT NULL,
            UNIQUE(discussion_id, turn_id)
        );

        CREATE TABLE IF NOT EXISTS decisions (
            decision_id     TEXT PRIMARY KEY,
            discussion_id   TEXT NOT NULL REFERENCES discussions(discussion_id),
            adr_path        TEXT NOT NULL,
            supersedes      TEXT,
            created_at      DATETIME NOT NULL,
            status          TEXT NOT NULL DEFAULT 'accepted'
                CHECK(status IN ('accepted', 'superseded', 'deprecated'))
        );

        CREATE TABLE IF NOT EXISTS reflections (
            reflection_id   TEXT PRIMARY KEY,
            discussion_id   TEXT NOT NULL REFERENCES discussions(discussion_id),
            agent           TEXT NOT NULL,
            missed_signal   TEXT,
            improvement_rule TEXT,
            confidence_delta REAL,
            promoted        BOOLEAN NOT NULL DEFAULT 0,
            created_at      DATETIME NOT NULL
        );

        CREATE TABLE IF NOT EXISTS education_results (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      TEXT NOT NULL,
            discussion_id   TEXT REFERENCES discussions(discussion_id),
            bloom_level     TEXT NOT NULL CHECK(bloom_level IN (
                'remember', 'understand', 'apply', 'analyze', 'evaluate', 'create'
            )),
            question_type   TEXT NOT NULL CHECK(question_type IN (
                'recall', 'walkthrough', 'debug-scenario', 'change-impact', 'explain-back'
            )),
            score           REAL NOT NULL CHECK(score >= 0.0 AND score <= 1.0),
            passed          BOOLEAN NOT NULL,
            timestamp       DATETIME NOT NULL
        );

        CREATE TABLE IF NOT EXISTS protocol_yield (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            discussion_id   TEXT NOT NULL REFERENCES discussions(discussion_id),
            protocol_type   TEXT NOT NULL CHECK(protocol_type IN (
                'review', 'checkpoint', 'education_gate', 'quality_gate', 'retro'
            )),
            findings_blocking   INTEGER NOT NULL DEFAULT 0,
            findings_advisory   INTEGER NOT NULL DEFAULT 0,
            findings_false_positive INTEGER NOT NULL DEFAULT 0,
            agent_turns_used    INTEGER NOT NULL DEFAULT 0,
            outcome         TEXT NOT NULL CHECK(outcome IN (
                'approve', 'approve-with-changes', 'request-changes', 'reject',
                'pass', 'fail', 'revise-resolved', 'revise-unresolved'
            )),
            timestamp       DATETIME NOT NULL
        );

        -- Indexes for common query patterns
        CREATE INDEX IF NOT EXISTS idx_turns_discussion ON turns(discussion_id);
        CREATE INDEX IF NOT EXISTS idx_turns_agent ON turns(agent);
        CREATE INDEX IF NOT EXISTS idx_turns_timestamp ON turns(timestamp);
        CREATE INDEX IF NOT EXISTS idx_decisions_discussion ON decisions(discussion_id);
        CREATE INDEX IF NOT EXISTS idx_reflections_discussion ON reflections(discussion_id);
        CREATE INDEX IF NOT EXISTS idx_reflections_agent ON reflections(agent);
        CREATE INDEX IF NOT EXISTS idx_education_session ON education_results(session_id);
        CREATE INDEX IF NOT EXISTS idx_education_discussion ON education_results(discussion_id);
        CREATE INDEX IF NOT EXISTS idx_discussions_status ON discussions(status);
        CREATE INDEX IF NOT EXISTS idx_discussions_created ON discussions(created_at);
        CREATE INDEX IF NOT EXISTS idx_protocol_yield_discussion ON protocol_yield(discussion_id);
        CREATE INDEX IF NOT EXISTS idx_protocol_yield_type ON protocol_yield(protocol_type);
    """)

    conn.commit()

    # Migration: add new columns to existing databases (safe — SQLite ignores if already present)
    for col, col_type in [("command_type", "TEXT"), ("duration_minutes", "REAL")]:
        try:
            conn.execute(f"ALTER TABLE discussions ADD COLUMN {col} {col_type}")
            print(f"  Migration: added discussions.{col}")
        except sqlite3.OperationalError:
            pass  # Column already exists

    conn.commit()
    conn.close()
    print(f"Database initialized at {db_path}")


if __name__ == "__main__":
    init_db()
