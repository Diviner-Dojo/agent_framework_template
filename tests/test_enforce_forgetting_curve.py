"""Tests for scripts/enforce_forgetting_curve.py.

Covers both thresholds (review at 90 days, archive at 180 days),
--dry-run mode, .gitkeep skip, NULL last_referenced_at fallback,
and injectable memory_dir/db_path parameters.
"""

import os
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Add project root to path for imports
TEMPLATE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(TEMPLATE_ROOT))

from scripts.enforce_forgetting_curve import enforce_forgetting_curve  # noqa: E402


def _set_mtime_days_ago(filepath: Path, days: int) -> None:
    """Set file modification time to N days ago."""
    target_time = datetime.now(UTC) - timedelta(days=days)
    timestamp = target_time.timestamp()
    os.utime(filepath, (timestamp, timestamp))


def _create_memory_structure(memory_dir: Path) -> None:
    """Create the standard memory subdirectory structure."""
    for subdir in ["decisions", "lessons", "patterns", "reflections", "rules", "bugs"]:
        (memory_dir / subdir).mkdir(parents=True, exist_ok=True)


class TestForgettingCurve:
    """Tests for the forgetting curve enforcement logic."""

    def test_fresh_files_not_flagged(self, tmp_path: Path) -> None:
        """Files younger than review_days should not be flagged."""
        memory_dir = tmp_path / "memory"
        _create_memory_structure(memory_dir)

        (memory_dir / "decisions" / "recent.md").write_text("fresh content")

        result = enforce_forgetting_curve(memory_dir=memory_dir, db_path=tmp_path / "nodb.db")
        assert result["flagged"] == []
        assert result["archived"] == []

    def test_review_threshold(self, tmp_path: Path) -> None:
        """Files older than review_days but younger than archive_days should be flagged."""
        memory_dir = tmp_path / "memory"
        _create_memory_structure(memory_dir)

        stale_file = memory_dir / "patterns" / "old-pattern.md"
        stale_file.write_text("stale content")
        _set_mtime_days_ago(stale_file, 100)

        result = enforce_forgetting_curve(memory_dir=memory_dir, db_path=tmp_path / "nodb.db")
        assert len(result["flagged"]) == 1
        assert "old-pattern.md" in result["flagged"][0]
        assert result["archived"] == []

    def test_archive_threshold(self, tmp_path: Path) -> None:
        """Files older than archive_days should be archived."""
        memory_dir = tmp_path / "memory"
        _create_memory_structure(memory_dir)

        ancient_file = memory_dir / "reflections" / "ancient.md"
        ancient_file.write_text("ancient content")
        _set_mtime_days_ago(ancient_file, 200)

        result = enforce_forgetting_curve(memory_dir=memory_dir, db_path=tmp_path / "nodb.db")
        assert len(result["archived"]) == 1
        assert "ancient.md" in result["archived"][0]
        # File should have been moved
        assert not ancient_file.exists()
        assert (memory_dir / "archive" / "reflections" / "ancient.md").exists()

    def test_dry_run_does_not_move(self, tmp_path: Path) -> None:
        """In dry-run mode, files should be reported but not moved."""
        memory_dir = tmp_path / "memory"
        _create_memory_structure(memory_dir)

        ancient_file = memory_dir / "decisions" / "old.md"
        ancient_file.write_text("old content")
        _set_mtime_days_ago(ancient_file, 200)

        result = enforce_forgetting_curve(
            dry_run=True, memory_dir=memory_dir, db_path=tmp_path / "nodb.db"
        )
        assert len(result["archived"]) == 1
        # File should NOT have been moved
        assert ancient_file.exists()

    def test_protected_files_not_archived(self, tmp_path: Path) -> None:
        """Protected files should never be archived regardless of age."""
        memory_dir = tmp_path / "memory"
        _create_memory_structure(memory_dir)

        protected = memory_dir / "lessons" / "adoption-log.md"
        protected.write_text("important content")
        _set_mtime_days_ago(protected, 365)

        result = enforce_forgetting_curve(memory_dir=memory_dir, db_path=tmp_path / "nodb.db")
        assert result["flagged"] == []
        assert result["archived"] == []
        assert protected.exists()

    def test_gitkeep_skipped(self, tmp_path: Path) -> None:
        """'.gitkeep' files should be skipped entirely."""
        memory_dir = tmp_path / "memory"
        _create_memory_structure(memory_dir)

        gitkeep = memory_dir / "patterns" / ".gitkeep"
        gitkeep.write_text("")
        _set_mtime_days_ago(gitkeep, 365)

        result = enforce_forgetting_curve(memory_dir=memory_dir, db_path=tmp_path / "nodb.db")
        assert result["flagged"] == []
        assert result["archived"] == []

    def test_missing_memory_dir(self, tmp_path: Path) -> None:
        """Should return empty result when memory directory doesn't exist."""
        result = enforce_forgetting_curve(
            memory_dir=tmp_path / "nonexistent", db_path=tmp_path / "nodb.db"
        )
        assert result == {"flagged": [], "archived": []}

    def test_custom_thresholds(self, tmp_path: Path) -> None:
        """Custom review_days and archive_days should be respected."""
        memory_dir = tmp_path / "memory"
        _create_memory_structure(memory_dir)

        f = memory_dir / "rules" / "custom.md"
        f.write_text("content")
        _set_mtime_days_ago(f, 15)

        result = enforce_forgetting_curve(
            review_days=10,
            archive_days=30,
            memory_dir=memory_dir,
            db_path=tmp_path / "nodb.db",
        )
        assert len(result["flagged"]) == 1

    def test_sqlite_last_referenced_at(self, tmp_path: Path) -> None:
        """Should use last_referenced_at from SQLite when available."""
        memory_dir = tmp_path / "memory"
        _create_memory_structure(memory_dir)

        # Create a file with recent mtime but old SQLite reference
        f = memory_dir / "patterns" / "db-tracked.md"
        f.write_text("content")
        # File mtime is recent (would not be flagged)

        # But SQLite says it was last referenced 100 days ago
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE promotion_candidates (source_file TEXT, last_referenced_at TEXT)"
        )
        old_date = (datetime.now(UTC) - timedelta(days=100)).isoformat()
        conn.execute(
            "INSERT INTO promotion_candidates VALUES (?, ?)",
            ("patterns/db-tracked.md", old_date),
        )
        conn.commit()
        conn.close()

        result = enforce_forgetting_curve(memory_dir=memory_dir, db_path=db_path)
        assert len(result["flagged"]) == 1

    def test_db_operational_error_falls_back_to_mtime(self, tmp_path: Path) -> None:
        """When DB exists but lacks promotion_candidates table, should fall back to mtime."""
        memory_dir = tmp_path / "memory"
        _create_memory_structure(memory_dir)

        f = memory_dir / "patterns" / "no-table.md"
        f.write_text("content")
        _set_mtime_days_ago(f, 100)

        # Create a DB without the expected table (triggers OperationalError)
        db_path = tmp_path / "broken.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE other_table (id INTEGER)")
        conn.commit()
        conn.close()

        result = enforce_forgetting_curve(memory_dir=memory_dir, db_path=db_path)
        # Should fall back to mtime (100 days) and flag for review
        assert len(result["flagged"]) == 1
        assert "no-table.md" in result["flagged"][0]

    def test_malformed_iso_date_skipped(self, tmp_path: Path) -> None:
        """When last_referenced_at has a non-ISO value, that row should be skipped."""
        memory_dir = tmp_path / "memory"
        _create_memory_structure(memory_dir)

        f = memory_dir / "patterns" / "bad-date.md"
        f.write_text("content")
        # Recent mtime — should not be flagged if malformed row is properly skipped

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE promotion_candidates (source_file TEXT, last_referenced_at TEXT)"
        )
        conn.execute(
            "INSERT INTO promotion_candidates VALUES (?, ?)",
            ("patterns/bad-date.md", "not-a-date"),
        )
        conn.commit()
        conn.close()

        result = enforce_forgetting_curve(memory_dir=memory_dir, db_path=db_path)
        # Malformed date skipped, falls back to recent mtime — should not be flagged
        assert result["flagged"] == []
        assert result["archived"] == []

    def test_null_last_referenced_at_falls_back_to_mtime(self, tmp_path: Path) -> None:
        """When last_referenced_at is NULL, should fall back to file mtime."""
        memory_dir = tmp_path / "memory"
        _create_memory_structure(memory_dir)

        f = memory_dir / "patterns" / "null-ref.md"
        f.write_text("content")
        # Recent mtime — should not be flagged even though DB has NULL

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE promotion_candidates (source_file TEXT, last_referenced_at TEXT)"
        )
        conn.execute(
            "INSERT INTO promotion_candidates VALUES (?, NULL)", ("patterns/null-ref.md",)
        )
        conn.commit()
        conn.close()

        result = enforce_forgetting_curve(memory_dir=memory_dir, db_path=db_path)
        # Recent mtime means it should not be flagged
        assert result["flagged"] == []
        assert result["archived"] == []
