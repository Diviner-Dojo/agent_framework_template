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

        -- Phase 4: Structured findings extraction
        CREATE TABLE IF NOT EXISTS findings (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            finding_id      TEXT NOT NULL UNIQUE,
            discussion_id   TEXT NOT NULL REFERENCES discussions(discussion_id),
            turn_id         INTEGER NOT NULL,
            agent           TEXT NOT NULL,
            severity        TEXT NOT NULL CHECK(severity IN (
                'critical', 'high', 'medium', 'low', 'info'
            )),
            category        TEXT NOT NULL CHECK(category IN (
                'security', 'architecture', 'performance', 'testing',
                'correctness', 'ux', 'documentation', 'process'
            )),
            summary         TEXT NOT NULL,
            content_excerpt TEXT NOT NULL,
            disposition     TEXT NOT NULL DEFAULT 'open' CHECK(disposition IN (
                'open', 'resolved', 'accepted-risk', 'carried-forward', 'promoted'
            )),
            resolution_ref  TEXT,
            tags            TEXT,
            created_at      DATETIME NOT NULL,
            promoted_at     DATETIME
        );

        -- Phase 4: Promotion candidate pipeline
        CREATE TABLE IF NOT EXISTS promotion_candidates (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id    TEXT NOT NULL UNIQUE,
            candidate_type  TEXT NOT NULL CHECK(candidate_type IN (
                'pattern', 'decision', 'reflection', 'rule', 'lesson'
            )),
            source_type     TEXT NOT NULL CHECK(source_type IN (
                'finding', 'reflection', 'retro', 'meta_review', 'adoption_log'
            )),
            source_refs     TEXT NOT NULL,
            title           TEXT NOT NULL,
            summary         TEXT NOT NULL,
            evidence_count  INTEGER NOT NULL DEFAULT 1,
            target_path     TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'pending' CHECK(status IN (
                'pending', 'approved', 'rejected', 'deferred'
            )),
            human_verdict   TEXT,
            created_at      DATETIME NOT NULL,
            reviewed_at     DATETIME,
            promoted_at     DATETIME,
            last_referenced_at DATETIME
        );

        -- Phase 5: Pattern mining and Rule of Three
        CREATE TABLE IF NOT EXISTS pattern_sightings (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_key     TEXT NOT NULL,
            finding_id      TEXT REFERENCES findings(finding_id),
            discussion_id   TEXT NOT NULL REFERENCES discussions(discussion_id),
            agent           TEXT NOT NULL,
            source_type     TEXT NOT NULL CHECK(source_type IN (
                'finding', 'reflection', 'retro', 'adoption_log'
            )),
            sighted_at      DATETIME NOT NULL
        );

        -- Phase 5: Agent effectiveness tracking
        CREATE TABLE IF NOT EXISTS agent_effectiveness (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            discussion_id   TEXT NOT NULL REFERENCES discussions(discussion_id),
            agent           TEXT NOT NULL,
            findings_produced   INTEGER NOT NULL DEFAULT 0,
            findings_unique     INTEGER NOT NULL DEFAULT 0,
            findings_survived   INTEGER NOT NULL DEFAULT 0,
            findings_dropped    INTEGER NOT NULL DEFAULT 0,
            confidence_avg      REAL,
            confidence_accuracy REAL,
            computed_at     DATETIME NOT NULL,
            UNIQUE(discussion_id, agent)
        );

        -- Phase 5: Rule of Three view
        CREATE VIEW IF NOT EXISTS v_rule_of_three AS
        SELECT pattern_key,
               COUNT(DISTINCT discussion_id) AS discussion_count,
               COUNT(DISTINCT agent) AS agent_count,
               MIN(sighted_at) AS first_seen,
               MAX(sighted_at) AS last_seen,
               GROUP_CONCAT(DISTINCT discussion_id) AS discussions
        FROM pattern_sightings
        GROUP BY pattern_key
        HAVING COUNT(DISTINCT discussion_id) >= 3;

        -- Phase 5: Agent dashboard view
        CREATE VIEW IF NOT EXISTS v_agent_dashboard AS
        SELECT agent,
               COUNT(*) AS discussions,
               SUM(findings_produced) AS total_findings,
               SUM(findings_unique) AS total_unique,
               ROUND(CAST(SUM(findings_unique) AS REAL) /
                   NULLIF(SUM(findings_produced), 0) * 100, 1) AS uniqueness_pct,
               ROUND(CAST(SUM(findings_survived) AS REAL) /
                   NULLIF(SUM(findings_produced), 0) * 100, 1) AS survival_pct,
               ROUND(AVG(confidence_avg), 3) AS avg_confidence,
               ROUND(AVG(confidence_accuracy), 3) AS avg_calibration
        FROM agent_effectiveness
        GROUP BY agent;

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
        CREATE INDEX IF NOT EXISTS idx_findings_agent ON findings(agent);
        CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity);
        CREATE INDEX IF NOT EXISTS idx_findings_category ON findings(category);
        CREATE INDEX IF NOT EXISTS idx_findings_disposition ON findings(disposition);
        CREATE INDEX IF NOT EXISTS idx_promotion_candidates_status ON promotion_candidates(status);
        CREATE INDEX IF NOT EXISTS idx_pattern_sightings_key ON pattern_sightings(pattern_key);
        CREATE INDEX IF NOT EXISTS idx_pattern_sightings_discussion ON pattern_sightings(discussion_id);
        CREATE INDEX IF NOT EXISTS idx_agent_effectiveness_discussion ON agent_effectiveness(discussion_id);
        CREATE INDEX IF NOT EXISTS idx_agent_effectiveness_agent ON agent_effectiveness(agent);
    """)

    conn.commit()

    # Migration: add new columns to existing databases (safe — SQLite ignores if already present)
    for col, col_type in [("command_type", "TEXT"), ("duration_minutes", "REAL")]:
        try:
            conn.execute(f"ALTER TABLE discussions ADD COLUMN {col} {col_type}")
            print(f"  Migration: added discussions.{col}")
        except sqlite3.OperationalError:
            pass  # Column already exists

    # Migration: add searchable content columns to turns table (Phase 4.2)
    for col, col_type in [("content_excerpt", "TEXT"), ("tags", "TEXT")]:
        try:
            conn.execute(f"ALTER TABLE turns ADD COLUMN {col} {col_type}")
            print(f"  Migration: added turns.{col}")
        except sqlite3.OperationalError:
            pass  # Column already exists

    conn.commit()
    conn.close()
    print(f"Database initialized at {db_path}")


if __name__ == "__main__":
    init_db()
