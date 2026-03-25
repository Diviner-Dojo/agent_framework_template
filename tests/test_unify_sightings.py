"""Tests for scripts/unify_sightings.py.

Covers duplicate detection, --dry-run mode, empty/missing adoption log,
normalization, and discussion validation.
"""

import sqlite3
import sys
from pathlib import Path

# Add project root to path for imports
TEMPLATE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(TEMPLATE_ROOT))
sys.path.insert(0, str(TEMPLATE_ROOT / "scripts"))

from scripts.unify_sightings import (  # noqa: E402
    _parse_adoption_log,
    normalize_pattern_key,
    unify_sightings,
)


def _create_test_db(db_path: Path) -> None:
    """Create a minimal test database with required tables."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS pattern_sightings ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  pattern_hash TEXT,"
        "  discussion_id TEXT,"
        "  category TEXT,"
        "  summary TEXT,"
        "  source TEXT,"
        "  created_at TEXT"
        ")"
    )
    conn.commit()
    conn.close()


def _create_adoption_log(log_path: Path, content: str) -> None:
    """Write adoption log content to a file."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(content, encoding="utf-8")


class TestNormalizePatternKey:
    """Tests for pattern key normalization."""

    def test_basic_normalization(self) -> None:
        key = normalize_pattern_key("Error Handling Pattern")
        assert "error" in key
        assert "handling" in key
        assert "pattern" in key

    def test_stop_word_removal(self) -> None:
        key = normalize_pattern_key("Use the error handling for the API")
        # "use", "the", "for" are stop words
        assert "use" not in key.split(":")
        assert "the" not in key.split(":")
        assert "for" not in key.split(":")

    def test_order_independence(self) -> None:
        key1 = normalize_pattern_key("Error Handling Pattern")
        key2 = normalize_pattern_key("Pattern Handling Error")
        assert key1 == key2

    def test_hyphen_underscore_normalized(self) -> None:
        key1 = normalize_pattern_key("error-handling")
        key2 = normalize_pattern_key("error_handling")
        assert key1 == key2

    def test_case_insensitive(self) -> None:
        key1 = normalize_pattern_key("ERROR HANDLING")
        key2 = normalize_pattern_key("error handling")
        assert key1 == key2

    def test_single_char_tokens_filtered(self) -> None:
        key = normalize_pattern_key("a b c error")
        # Single-char tokens should be filtered
        assert "a" not in key.split(":")
        assert "error" in key


class TestParseAdoptionLog:
    """Tests for parsing the adoption log."""

    def test_missing_file(self, tmp_path: Path) -> None:
        result = _parse_adoption_log(tmp_path / "nonexistent.md")
        assert result == []

    def test_empty_file(self, tmp_path: Path) -> None:
        log = tmp_path / "adoption-log.md"
        log.write_text("# Empty log\n", encoding="utf-8")
        result = _parse_adoption_log(log)
        assert result == []

    def test_parses_table_rows(self, tmp_path: Path) -> None:
        content = (
            "# Adoption Log\n\n"
            "| Pattern | Source | Category | Status |\n"
            "|---------|--------|----------|--------|\n"
            "| Error Hierarchy | project-a | error-handling | ADOPTED |\n"
            "| Rate Limiting | project-b | security | PENDING |\n"
        )
        log = tmp_path / "adoption-log.md"
        log.write_text(content, encoding="utf-8")
        result = _parse_adoption_log(log)
        assert len(result) == 2
        assert result[0]["name"] == "Error Hierarchy"
        assert result[1]["category"] == "security"

    def test_detects_duplicates(self, tmp_path: Path) -> None:
        """Duplicate patterns (same normalized key) should be deduplicated."""
        content = (
            "| Pattern | Source | Category |\n"
            "|---------|--------|----------|\n"
            "| Error Handling | project-a | errors |\n"
            "| Handling Error | project-b | errors |\n"
        )
        log = tmp_path / "adoption-log.md"
        log.write_text(content, encoding="utf-8")
        result = _parse_adoption_log(log)
        # Both normalize to the same key, so only the first should be kept
        assert len(result) == 1


class TestUnifySightings:
    """Tests for the main unify_sightings function."""

    def test_missing_database(self, tmp_path: Path) -> None:
        result = unify_sightings(db_path=tmp_path / "nodb.db", log_path=tmp_path / "nolog.md")
        assert result == 0

    def test_empty_log(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        _create_test_db(db_path)
        log_path = tmp_path / "empty.md"
        log_path.write_text("# Empty\n", encoding="utf-8")

        result = unify_sightings(db_path=db_path, log_path=log_path)
        assert result == 0

    def test_inserts_new_sightings(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        _create_test_db(db_path)

        content = (
            "| Pattern | Source | Category |\n"
            "|---------|--------|----------|\n"
            "| Test Pattern | project-a | testing |\n"
        )
        log_path = tmp_path / "adoption-log.md"
        log_path.write_text(content, encoding="utf-8")

        result = unify_sightings(db_path=db_path, log_path=log_path)
        assert result == 1

        # Verify in database
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT * FROM pattern_sightings").fetchall()
        conn.close()
        assert len(rows) == 1

    def test_dry_run_does_not_insert(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        _create_test_db(db_path)

        content = (
            "| Pattern | Source | Category |\n"
            "|---------|--------|----------|\n"
            "| Test Pattern | project-a | testing |\n"
        )
        log_path = tmp_path / "adoption-log.md"
        log_path.write_text(content, encoding="utf-8")

        result = unify_sightings(dry_run=True, db_path=db_path, log_path=log_path)
        assert result == 1  # Reports count

        # But nothing in the database
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT * FROM pattern_sightings").fetchall()
        conn.close()
        assert len(rows) == 0

    def test_no_duplicate_inserts(self, tmp_path: Path) -> None:
        """Running twice should not create duplicate entries."""
        db_path = tmp_path / "test.db"
        _create_test_db(db_path)

        content = (
            "| Pattern | Source | Category |\n"
            "|---------|--------|----------|\n"
            "| Test Pattern | project-a | testing |\n"
        )
        log_path = tmp_path / "adoption-log.md"
        log_path.write_text(content, encoding="utf-8")

        # Run twice
        unify_sightings(db_path=db_path, log_path=log_path)
        result2 = unify_sightings(db_path=db_path, log_path=log_path)
        assert result2 == 0  # No new insertions

        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT * FROM pattern_sightings").fetchall()
        conn.close()
        assert len(rows) == 1
