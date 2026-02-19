"""Tests for scripts/backup_utils.py — backup-before-modify utilities."""

import time

import pytest

from scripts.backup_utils import (
    _validate_path_containment,
    backup_file,
    detect_conflicts,
    prune_backups,
    restore_latest,
)


@pytest.fixture
def project_dir(tmp_path):
    """Create a temporary project directory with structure."""
    (tmp_path / "CLAUDE.md").write_text("# Project Constitution\nOriginal content.")
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "test_rule.md").write_text("Original rule content.")
    memory_dir = tmp_path / "memory" / "lessons"
    memory_dir.mkdir(parents=True)
    (memory_dir / "adoption-log.md").write_text("# Adoption Log\nOriginal.")
    return tmp_path


class TestPathContainment:
    """Test path traversal prevention."""

    def test_valid_path_within_project(self, project_dir) -> None:
        file_path = project_dir / "CLAUDE.md"
        result = _validate_path_containment(file_path, project_dir)
        assert result == file_path.resolve()

    def test_path_traversal_blocked(self, project_dir) -> None:
        evil_path = project_dir / ".." / ".." / "etc" / "hosts"
        with pytest.raises(ValueError, match="Path traversal blocked"):
            _validate_path_containment(evil_path, project_dir)

    def test_double_dot_traversal_blocked(self, project_dir) -> None:
        evil_path = project_dir / "memory" / ".." / ".." / "sensitive"
        with pytest.raises(ValueError, match="Path traversal blocked"):
            _validate_path_containment(evil_path, project_dir)

    def test_subdirectory_allowed(self, project_dir) -> None:
        sub_path = project_dir / ".claude" / "rules" / "test_rule.md"
        result = _validate_path_containment(sub_path, project_dir)
        assert result == sub_path.resolve()


class TestBackupFile:
    """Test backup_file() functionality."""

    def test_creates_backup(self, project_dir) -> None:
        source = project_dir / "CLAUDE.md"
        backup_path = backup_file(source, project_root=project_dir)
        assert backup_path is not None
        assert backup_path.exists()
        assert backup_path.read_text() == "# Project Constitution\nOriginal content."

    def test_backup_filename_format(self, project_dir) -> None:
        source = project_dir / "CLAUDE.md"
        backup_path = backup_file(source, project_root=project_dir)
        assert backup_path is not None
        assert backup_path.suffix == ".bak"
        assert "CLAUDE.md" in backup_path.name

    def test_backup_nested_file(self, project_dir) -> None:
        source = project_dir / ".claude" / "rules" / "test_rule.md"
        backup_path = backup_file(source, project_root=project_dir)
        assert backup_path is not None
        assert backup_path.exists()
        assert backup_path.read_text() == "Original rule content."

    def test_backup_nonexistent_returns_none(self, project_dir) -> None:
        source = project_dir / "does_not_exist.md"
        result = backup_file(source, project_root=project_dir)
        assert result is None

    def test_multiple_backups_unique(self, project_dir) -> None:
        source = project_dir / "CLAUDE.md"
        b1 = backup_file(source, project_root=project_dir)
        time.sleep(1.1)  # Ensure different timestamps
        b2 = backup_file(source, project_root=project_dir)
        assert b1 != b2
        assert b1 is not None
        assert b2 is not None
        assert b1.exists() and b2.exists()

    def test_path_traversal_blocked(self, project_dir) -> None:
        evil_path = project_dir / ".." / ".." / "etc" / "passwd"
        with pytest.raises(ValueError, match="Path traversal blocked"):
            backup_file(evil_path, project_root=project_dir)


class TestRestoreLatest:
    """Test restore_latest() functionality."""

    def test_restores_from_backup(self, project_dir) -> None:
        source = project_dir / "CLAUDE.md"
        original = source.read_text()

        # Backup, then modify
        backup_file(source, project_root=project_dir)
        source.write_text("Modified content that is wrong.")

        # Restore
        restored_from = restore_latest(source, project_root=project_dir)
        assert restored_from is not None
        assert source.read_text() == original

    def test_restores_most_recent(self, project_dir) -> None:
        source = project_dir / "CLAUDE.md"

        # First backup (original content)
        backup_file(source, project_root=project_dir)
        time.sleep(1.1)

        # Modify and second backup
        source.write_text("Version 2")
        backup_file(source, project_root=project_dir)
        time.sleep(1.1)

        # Modify again
        source.write_text("Version 3 — broken")

        # Restore should get Version 2 (most recent backup)
        restore_latest(source, project_root=project_dir)
        assert source.read_text() == "Version 2"

    def test_no_backup_returns_none(self, project_dir) -> None:
        source = project_dir / "CLAUDE.md"
        result = restore_latest(source, project_root=project_dir)
        assert result is None

    def test_path_traversal_blocked(self, project_dir) -> None:
        evil_path = project_dir / ".." / ".." / "etc" / "passwd"
        with pytest.raises(ValueError, match="Path traversal blocked"):
            restore_latest(evil_path, project_root=project_dir)


class TestDetectConflicts:
    """Test detect_conflicts() functionality."""

    def test_no_conflict_when_content_present(self, project_dir) -> None:
        source = project_dir / "CLAUDE.md"
        assert detect_conflicts(source, "Original content", project_root=project_dir) is False

    def test_conflict_when_content_missing(self, project_dir) -> None:
        source = project_dir / "CLAUDE.md"
        assert (
            detect_conflicts(source, "This text is not in the file", project_root=project_dir)
            is True
        )

    def test_conflict_when_file_missing(self, project_dir) -> None:
        source = project_dir / "nonexistent.md"
        assert detect_conflicts(source, "anything", project_root=project_dir) is True

    def test_conflict_after_external_modification(self, project_dir) -> None:
        source = project_dir / "CLAUDE.md"
        expected = "Original content"
        # Verify no conflict initially
        assert detect_conflicts(source, expected, project_root=project_dir) is False
        # Simulate external modification
        source.write_text("Completely different content.")
        # Now there's a conflict
        assert detect_conflicts(source, expected, project_root=project_dir) is True

    def test_path_traversal_blocked(self, project_dir) -> None:
        evil_path = project_dir / ".." / ".." / "etc" / "passwd"
        with pytest.raises(ValueError, match="Path traversal blocked"):
            detect_conflicts(evil_path, "anything", project_root=project_dir)


class TestPruneBackups:
    """Test prune_backups() functionality."""

    def test_prune_removes_old_backups(self, project_dir) -> None:
        source = project_dir / "CLAUDE.md"
        backup_path = backup_file(source, project_root=project_dir)
        assert backup_path is not None

        # Prune with 0 retention (everything is "old")
        removed = prune_backups(retention_seconds=0, project_root=project_dir)
        assert removed == 1
        assert not backup_path.exists()

    def test_prune_keeps_recent_backups(self, project_dir) -> None:
        source = project_dir / "CLAUDE.md"
        backup_path = backup_file(source, project_root=project_dir)
        assert backup_path is not None

        # Prune with large retention (nothing is old)
        removed = prune_backups(retention_seconds=999999, project_root=project_dir)
        assert removed == 0
        assert backup_path.exists()

    def test_prune_empty_dir(self, project_dir) -> None:
        removed = prune_backups(retention_seconds=0, project_root=project_dir)
        assert removed == 0
