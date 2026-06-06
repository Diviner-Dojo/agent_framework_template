"""Initialize the Layer 2 SQLite relational index.

Creates metrics/evaluation.db with all framework tables.
Safe to run multiple times — uses CREATE TABLE IF NOT EXISTS.
"""

import re
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "metrics" / "evaluation.db"

# Allowlist for the ALTER TABLE migration loop. SQLite cannot bind DDL
# identifiers (`?` is values-only), so they are interpolated — these sets make
# the safety explicit and fail loudly if a future entry ever sources an
# identifier from config/input (security review B1).
_MIGRATION_ALLOWED_TABLES = {"discussions", "turns"}
_MIGRATION_ALLOWED_TYPES = {"TEXT", "REAL", "INTEGER", "TEXT DEFAULT '[]'"}
_MIGRATION_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _assert_safe_migration(table: str, column: str, col_type: str) -> None:
    """Reject any ALTER TABLE identifier not on the allowlist (DDL can't bind).

    Raises:
        ValueError: if the table, column, or column type is not allowlisted.
    """
    if (
        table not in _MIGRATION_ALLOWED_TABLES
        or not _MIGRATION_IDENT.match(column)
        or col_type not in _MIGRATION_ALLOWED_TYPES
    ):
        raise ValueError(f"Unsafe migration target rejected: {table}.{column} {col_type}")


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

        -- Lineage tracking tables (Steward Phase 1)

        CREATE TABLE IF NOT EXISTS lineage_nodes (
            id              TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            type            TEXT NOT NULL CHECK(type IN ('template', 'derived', 'soft-fork', 'hard-fork')),
            created_at      TEXT NOT NULL,
            current_version TEXT NOT NULL,
            upstream_version TEXT,
            metadata        TEXT
        );

        CREATE TABLE IF NOT EXISTS lineage_file_drift (
            lineage_id      TEXT NOT NULL REFERENCES lineage_nodes(id),
            file_path       TEXT NOT NULL,
            drift_status    TEXT NOT NULL CHECK(drift_status IN (
                'current', 'modified', 'pinned', 'deleted', 'added'
            )),
            is_intentional  BOOLEAN DEFAULT FALSE,
            pin_reason      TEXT,
            adr_reference   TEXT,
            template_hash   TEXT,
            local_hash      TEXT,
            last_checked    TEXT NOT NULL,
            PRIMARY KEY (lineage_id, file_path)
        );

        -- Telemetry & Oversight (Layer A — see ADR-0013, amended).
        -- Per-discussion, per-model token breakdown: the COST INPUT for
        -- per-tier dollar cost. Dollar cost is NEVER stored — it is computed at
        -- analysis time from config/model_pricing.yaml (ADR-0013 compute-don't-
        -- store). 'tier' is resolved from the model id at ingest; the literal
        -- 'unknown' is honest and is never silently zero-rated downstream.
        CREATE TABLE IF NOT EXISTS discussion_model_tokens (
            discussion_id       TEXT NOT NULL REFERENCES discussions(discussion_id),
            model_id            TEXT NOT NULL,
            tier                TEXT NOT NULL,
            tokens_in           INTEGER,
            tokens_out          INTEGER,
            cache_read_tokens   INTEGER,
            cache_create_tokens INTEGER,
            message_count       INTEGER NOT NULL DEFAULT 0,
            computed_at         DATETIME NOT NULL,
            PRIMARY KEY (discussion_id, model_id)
        );

        -- Watermark / run-state for incremental telemetry analysis (R-A4).
        -- e.g. key='cost_last_analyzed_at' -> ISO 8601 of the newest discussion
        -- closed_at processed, so subsequent runs skip already-analyzed history.
        -- Layer A2 adds key='failures_last_analyzed_mtime' -> the newest session
        -- transcript file mtime (epoch seconds) processed, so a re-run only
        -- re-parses session files that changed (the mtime watermark; ADR-0020).
        CREATE TABLE IF NOT EXISTS telemetry_run_state (
            key         TEXT PRIMARY KEY,
            value       TEXT,
            updated_at  DATETIME NOT NULL
        );

        -- Telemetry & Oversight (Layer A2 — failure/waste signals, ADR-0020).
        -- One row per detected failure signal, keyed by (session, type,
        -- signature) so re-analysis of a session is idempotent (DELETE-then-
        -- INSERT per session, like discussion_model_tokens). Compute-don't-store
        -- (ADR-0013): we persist the WASTED token counts + tier (the cost
        -- INPUT) and never a dollar figure — the cost-weight used for ranking is
        -- derived at read time from config/model_pricing.yaml. 'tier' may be the
        -- literal 'unknown' (honest; never silently zero-rated downstream).
        --   failure_type: 'orphaned_subagent' | 'retry_loop'
        --   signature:    dedup key within a session (tool+input hash, or agentId)
        --   occurrence_count: repeats in a retry loop (>=1)
        CREATE TABLE IF NOT EXISTS telemetry_failures (
            id                          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id                  TEXT NOT NULL,
            discussion_id               TEXT,
            failure_type                TEXT NOT NULL CHECK(failure_type IN (
                'orphaned_subagent', 'retry_loop'
            )),
            signature                   TEXT NOT NULL,
            occurrence_count            INTEGER NOT NULL DEFAULT 1,
            tier                        TEXT NOT NULL,
            wasted_tokens_in            INTEGER,
            wasted_tokens_out           INTEGER,
            wasted_cache_read_tokens    INTEGER,
            wasted_cache_create_tokens  INTEGER,
            detail                      TEXT,
            first_seen                  DATETIME,
            last_seen                   DATETIME,
            computed_at                 DATETIME NOT NULL,
            UNIQUE(session_id, failure_type, signature)
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
        CREATE INDEX IF NOT EXISTS idx_lineage_file_drift_lineage ON lineage_file_drift(lineage_id);
        CREATE INDEX IF NOT EXISTS idx_lineage_file_drift_status ON lineage_file_drift(drift_status);
        CREATE INDEX IF NOT EXISTS idx_dmt_discussion ON discussion_model_tokens(discussion_id);
        CREATE INDEX IF NOT EXISTS idx_dmt_tier ON discussion_model_tokens(tier);
        CREATE INDEX IF NOT EXISTS idx_tf_session ON telemetry_failures(session_id);
        CREATE INDEX IF NOT EXISTS idx_tf_type ON telemetry_failures(failure_type);
        CREATE INDEX IF NOT EXISTS idx_tf_discussion ON telemetry_failures(discussion_id);
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

        -- Token efficiency: blocking findings per 1K output tokens by command_type.
        -- Cost is intentionally NOT stored — see ADR-0013. Pricing lives in
        -- config/model_pricing.yaml and is applied at analysis time, not capture time.
        --
        -- protocol_yield is pre-aggregated in a CTE so the LEFT JOIN is 1:1.
        -- Without this, a discussion with multiple protocol_yield rows (e.g. a
        -- /build_module run with checkpoint records) would fan out and bias
        -- AVG(total_tokens_*) by sampling each value once per yield row.
        CREATE VIEW IF NOT EXISTS v_token_efficiency AS
        WITH py_agg AS (
            SELECT
                discussion_id,
                SUM(findings_blocking) AS findings_blocking,
                SUM(findings_advisory) AS findings_advisory
            FROM protocol_yield
            GROUP BY discussion_id
        )
        SELECT
            d.command_type,
            COUNT(DISTINCT d.discussion_id) AS run_count,
            ROUND(AVG(d.total_tokens_in), 0) AS avg_tokens_in,
            ROUND(AVG(d.total_tokens_out), 0) AS avg_tokens_out,
            ROUND(AVG(d.total_cache_tokens), 0) AS avg_cache_tokens,
            SUM(py.findings_blocking) AS total_blocking,
            SUM(py.findings_advisory) AS total_advisory,
            ROUND(
                CAST(SUM(py.findings_blocking) AS REAL) * 1000.0 /
                NULLIF(SUM(d.total_tokens_out), 0),
                3
            ) AS blocking_per_1k_output_tokens
        FROM discussions d
        LEFT JOIN py_agg py ON py.discussion_id = d.discussion_id
        WHERE d.total_tokens_out IS NOT NULL
        GROUP BY d.command_type
        ORDER BY blocking_per_1k_output_tokens DESC;
    """)

    conn.commit()

    # Migration guards: add new columns to existing databases that lack them.
    # Each ALTER TABLE is wrapped in try/except so it's safe to run repeatedly.
    _migrations = [
        ("discussions", "command_type", "TEXT"),
        ("discussions", "duration_minutes", "REAL"),
        ("turns", "content_excerpt", "TEXT"),
        ("turns", "tags", "TEXT DEFAULT '[]'"),
        ("discussions", "related_discussion_id", "TEXT"),
        # ADR-0013: token-efficiency telemetry.
        # NULL is honest for historical rows — see ADR.
        ("turns", "tokens_in", "INTEGER"),
        ("turns", "tokens_out", "INTEGER"),
        ("turns", "cache_read_tokens", "INTEGER"),
        ("turns", "cache_create_tokens", "INTEGER"),
        ("discussions", "total_tokens_in", "INTEGER"),
        ("discussions", "total_tokens_out", "INTEGER"),
        ("discussions", "total_cache_tokens", "INTEGER"),
    ]
    # DDL identifiers are interpolated (SQLite can't bind them); the allowlist
    # guard fails loudly if a future entry is ever non-literal (security B1; the
    # same guard should be mirrored into ingest_token_usage._ensure_token_columns).
    for table, column, col_type in _migrations:
        _assert_safe_migration(table, column, col_type)
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists

    conn.close()
    print(f"Database initialized at {db_path}")


if __name__ == "__main__":
    init_db()
