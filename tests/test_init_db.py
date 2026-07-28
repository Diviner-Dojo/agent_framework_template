"""Regression tests for scripts/init_db.py schema initialization.

Ported from the v4 rebuild's deleted tests/test_telemetry.py (ADR-0029). The
telemetry *analyzers* were removed; their tables remain in the schema, and
these guards protect `init_db` itself, which is very much alive.

Two ledger entries depend on this file:

- Idempotent migration canary. `init_db()` must be safe to re-run and must add
  missing tables to a pre-existing database. The broad `except
  sqlite3.OperationalError` around the ALTER `_migrations` list swallows *all*
  operational errors, so these tests assert columns actually EXIST via
  `PRAGMA table_info` rather than merely that nothing raised.
- Migration allowlist (security B1). The ALTER loop interpolates DDL
  identifiers because SQLite cannot bind them; `_assert_safe_migration` must
  reject anything off-allowlist loudly.

Do not weaken either without an ADR addressing the swallow-all guard.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from scripts.init_db import _assert_safe_migration, init_db


def _make_db(tmp_path: Path) -> Path:
    """Create a fully initialized database."""
    db_path = tmp_path / "evaluation.db"
    init_db(db_path, quiet=True)
    return db_path


def _columns(db_path: Path, table: str) -> set[str]:
    """Return the column names of a table."""
    conn = sqlite3.connect(str(db_path))
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


def _all_tables(db_path: Path) -> set[str]:
    """Return every table name in the database."""
    conn = sqlite3.connect(str(db_path))
    try:
        return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()


@pytest.mark.regression
class TestSchemaMigration:
    """Canary for the swallow-all OperationalError guard on the ALTER loop."""

    def test_fresh_db_has_telemetry_tables(self, tmp_path):
        db_path = _make_db(tmp_path)
        assert "tier" in _columns(db_path, "discussion_model_tokens")
        assert {"cache_read_tokens", "cache_create_tokens"} <= _columns(
            db_path, "discussion_model_tokens"
        )
        assert "value" in _columns(db_path, "telemetry_run_state")

    def test_existing_db_without_table_gets_it(self, tmp_path):
        db_path = _make_db(tmp_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute("DROP TABLE discussion_model_tokens")
        conn.execute("DROP TABLE telemetry_run_state")
        conn.commit()
        conn.close()
        assert "discussion_model_tokens" not in _all_tables(db_path)

        init_db(db_path, quiet=True)

        assert "discussion_model_tokens" in _all_tables(db_path)
        assert "telemetry_run_state" in _all_tables(db_path)

    def test_existing_db_with_table_is_idempotent(self, tmp_path):
        db_path = _make_db(tmp_path)
        before = _columns(db_path, "discussion_model_tokens")
        init_db(db_path, quiet=True)
        assert _columns(db_path, "discussion_model_tokens") == before

    def test_briefings_table_added_to_pre_v4_db(self, tmp_path):
        """A v3 database gains the v4 education ledger on re-init."""
        db_path = _make_db(tmp_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute("DROP TABLE briefings")
        conn.commit()
        conn.close()

        init_db(db_path, quiet=True)

        assert "briefings" in _all_tables(db_path)


@pytest.mark.regression
class TestMigrationAllowlist:
    """Security B1: DDL identifiers are interpolated, so they must be validated."""

    def test_known_good_migration_is_accepted(self):
        _assert_safe_migration("turns", "tokens_in", "INTEGER")

    @pytest.mark.parametrize(
        ("table", "column", "col_type"),
        [
            ("turns; DROP TABLE turns", "x", "TEXT"),
            ("turns", "x) --", "TEXT"),
            ("turns", "x", "TEXT; DROP TABLE turns"),
        ],
    )
    def test_unsafe_identifiers_are_rejected(self, table, column, col_type):
        with pytest.raises(ValueError):
            _assert_safe_migration(table, column, col_type)
