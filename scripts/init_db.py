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

        -- Knowledge pipeline tables

        CREATE TABLE IF NOT EXISTS findings (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            discussion_id   TEXT NOT NULL REFERENCES discussions(discussion_id),
            turn_id         INTEGER NOT NULL,
            agent           TEXT NOT NULL,
            severity        TEXT NOT NULL CHECK(severity IN ('critical', 'high', 'medium', 'low', 'info')),
            category        TEXT NOT NULL,
            summary         TEXT NOT NULL,
            raw_excerpt     TEXT,
            resolved        BOOLEAN NOT NULL DEFAULT 0,
            created_at      DATETIME NOT NULL
        );

        CREATE TABLE IF NOT EXISTS promotion_candidates (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            finding_pattern TEXT NOT NULL,
            category        TEXT NOT NULL,
            sighting_count  INTEGER NOT NULL DEFAULT 1,
            first_seen      DATETIME NOT NULL,
            last_seen       DATETIME NOT NULL,
            promoted        BOOLEAN NOT NULL DEFAULT 0,
            promoted_at     DATETIME,
            promoted_to     TEXT,
            evidence_ids    TEXT NOT NULL DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS pattern_sightings (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_hash    TEXT NOT NULL,
            discussion_id   TEXT,
            category        TEXT NOT NULL,
            summary         TEXT NOT NULL,
            source          TEXT NOT NULL CHECK(source IN ('discussion', 'adoption-log', 'manual')),
            created_at      DATETIME NOT NULL
        );

        CREATE TABLE IF NOT EXISTS agent_effectiveness (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            agent           TEXT NOT NULL,
            discussion_id   TEXT NOT NULL REFERENCES discussions(discussion_id),
            findings_unique INTEGER NOT NULL DEFAULT 0,
            findings_duplicate INTEGER NOT NULL DEFAULT 0,
            findings_false_positive INTEGER NOT NULL DEFAULT 0,
            confidence_avg  REAL,
            confidence_calibration REAL,
            computed_at     DATETIME NOT NULL
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
        CREATE INDEX IF NOT EXISTS idx_findings_discussion ON findings(discussion_id);
        CREATE INDEX IF NOT EXISTS idx_findings_category ON findings(category);
        CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity);
        CREATE INDEX IF NOT EXISTS idx_pattern_sightings_hash ON pattern_sightings(pattern_hash);
        CREATE INDEX IF NOT EXISTS idx_pattern_sightings_discussion ON pattern_sightings(discussion_id);
        CREATE INDEX IF NOT EXISTS idx_agent_effectiveness_agent ON agent_effectiveness(agent);
        CREATE INDEX IF NOT EXISTS idx_agent_effectiveness_discussion ON agent_effectiveness(discussion_id);
        CREATE INDEX IF NOT EXISTS idx_promotion_candidates_category ON promotion_candidates(category);
    """)

    # Create views for knowledge pipeline reporting
    conn.executescript("""
        CREATE VIEW IF NOT EXISTS v_rule_of_three AS
        SELECT
            category,
            pattern_hash,
            summary,
            COUNT(DISTINCT discussion_id) AS sighting_count,
            MIN(created_at) AS first_seen,
            MAX(created_at) AS last_seen,
            GROUP_CONCAT(DISTINCT discussion_id) AS discussion_ids
        FROM pattern_sightings
        GROUP BY pattern_hash
        HAVING COUNT(DISTINCT discussion_id) >= 3
        ORDER BY sighting_count DESC;

        CREATE VIEW IF NOT EXISTS v_agent_dashboard AS
        SELECT
            ae.agent,
            COUNT(DISTINCT ae.discussion_id) AS discussions_participated,
            SUM(ae.findings_unique) AS total_unique_findings,
            SUM(ae.findings_duplicate) AS total_duplicate_findings,
            SUM(ae.findings_false_positive) AS total_false_positives,
            ROUND(AVG(ae.confidence_avg), 3) AS avg_confidence,
            ROUND(AVG(ae.confidence_calibration), 3) AS avg_calibration,
            ROUND(
                CAST(SUM(ae.findings_unique) AS REAL) /
                NULLIF(SUM(ae.findings_unique) + SUM(ae.findings_duplicate), 0),
                3
            ) AS uniqueness_ratio
        FROM agent_effectiveness ae
        GROUP BY ae.agent
        ORDER BY total_unique_findings DESC;
    """)

    conn.commit()

    # Migration guards: add new columns to existing databases that lack them.
    # Each ALTER TABLE is wrapped in try/except so it's safe to run repeatedly.
    _migrations = [
        ("discussions", "command_type", "TEXT"),
        ("discussions", "duration_minutes", "REAL"),
        ("turns", "content_excerpt", "TEXT"),
        ("turns", "tags", "TEXT DEFAULT '[]'"),
    ]
    for table, column, col_type in _migrations:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists

    conn.close()
    print(f"Database initialized at {db_path}")


if __name__ == "__main__":
    init_db()
