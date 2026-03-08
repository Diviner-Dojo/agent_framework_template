"""Backup-before-modify utilities for framework file safety.

Provides backup, restore, and conflict detection for framework files
(.claude/rules/, CLAUDE.md, memory/). Every modification to these files
should be preceded by a backup call, enabling one-command rollback.

Pattern source: daegwang/self-learning-agent (rules/patcher.ts)
Adopted: ANALYSIS-20260219-042113-self-learning-agent

Security: All operations validate that target paths resolve within the
project root to prevent path traversal attacks.
"""

import shutil
import time
from pathlib import Path

# Default backup retention: 90 days (seconds)
DEFAULT_RETENTION_SECONDS = 90 * 24 * 60 * 60

# Default backup directory relative to project root
DEFAULT_BACKUP_DIR = Path(".claude") / "hooks" / ".backups"


def _resolve_project_root() -> Path:
    """Resolve the project root directory."""
    env_dir = None
    try:
        import os

        env_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    except ImportError:
        pass
    if env_dir:
        return Path(env_dir).resolve()
    # Walk up from this script's location to find project root
    candidate = Path(__file__).resolve().parent.parent
    if (candidate / "CLAUDE.md").exists():
        return candidate
    return Path.cwd().resolve()


def _validate_path_containment(file_path: Path, project_root: Path) -> Path:
    """Validate that file_path resolves within project_root.

    Args:
        file_path: The path to validate.
        project_root: The project root boundary.

    Returns:
        The resolved, validated path.

    Raises:
        ValueError: If the path resolves outside the project root.
    """
    resolved = file_path.resolve()
    root_resolved = project_root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        raise ValueError(
            f"Path traversal blocked: '{file_path}' resolves to '{resolved}' "
            f"which is outside project root '{root_resolved}'"
        ) from None
    return resolved


def _get_backup_dir(project_root: Path | None = None) -> Path:
    """Get the backup directory, creating it if needed."""
    root = project_root or _resolve_project_root()
    backup_dir = root / DEFAULT_BACKUP_DIR
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def backup_file(
    file_path: str | Path,
    project_root: Path | None = None,
) -> Path | None:
    """Create a timestamped backup of a file before modification.

    Args:
        file_path: Path to the file to back up.
        project_root: Project root for path validation. Auto-detected if None.

    Returns:
        Path to the backup file, or None if the source doesn't exist.

    Raises:
        ValueError: If file_path resolves outside the project root.
    """
    root = (project_root or _resolve_project_root()).resolve()
    source = _validate_path_containment(Path(file_path), root)

    if not source.exists():
        return None

    backup_dir = _get_backup_dir(root)
    # Create a safe filename from the relative path
    rel_path = source.relative_to(root)
    safe_name = str(rel_path).replace("/", "_").replace("\\", "_")
    timestamp = int(time.time())
    backup_path = backup_dir / f"{safe_name}.{timestamp}.bak"

    shutil.copy2(source, backup_path)
    return backup_path


def restore_latest(
    file_path: str | Path,
    project_root: Path | None = None,
) -> Path | None:
    """Restore a file from its most recent backup.

    Args:
        file_path: Path to the file to restore.
        project_root: Project root for path validation. Auto-detected if None.

    Returns:
        Path to the backup that was restored from, or None if no backup exists.

    Raises:
        ValueError: If file_path resolves outside the project root.
    """
    root = (project_root or _resolve_project_root()).resolve()
    target = _validate_path_containment(Path(file_path), root)

    backup_dir = _get_backup_dir(root)
    rel_path = target.relative_to(root)
    safe_name = str(rel_path).replace("/", "_").replace("\\", "_")

    # Find all backups for this file, sorted by timestamp (newest first)
    backups = sorted(
        backup_dir.glob(f"{safe_name}.*.bak"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not backups:
        return None

    latest = backups[0]
    shutil.copy2(latest, target)
    return latest


def detect_conflicts(
    file_path: str | Path,
    expected_content: str,
    project_root: Path | None = None,
) -> bool:
    """Check if a file still contains the expected content before patching.

    Use this before modifying a file to verify that the content you intend
    to replace hasn't been changed by another session or manual edit.

    Args:
        file_path: Path to the file to check.
        expected_content: The content string expected to be present.
        project_root: Project root for path validation. Auto-detected if None.

    Returns:
        True if a conflict is detected (expected content NOT found).
        False if no conflict (expected content IS found, safe to proceed).

    Raises:
        ValueError: If file_path resolves outside the project root.
    """
    root = (project_root or _resolve_project_root()).resolve()
    target = _validate_path_containment(Path(file_path), root)

    if not target.exists():
        return True  # File missing = conflict

    current = target.read_text(encoding="utf-8")
    return expected_content not in current


def prune_backups(
    retention_seconds: int = DEFAULT_RETENTION_SECONDS,
    project_root: Path | None = None,
) -> int:
    """Remove backups older than the retention period.

    Args:
        retention_seconds: Maximum age of backups in seconds. Default 90 days.
        project_root: Project root. Auto-detected if None.

    Returns:
        Number of backup files removed.
    """
    root = (project_root or _resolve_project_root()).resolve()
    backup_dir = _get_backup_dir(root)
    cutoff = time.time() - retention_seconds
    removed = 0

    for backup_file in backup_dir.glob("*.bak"):
        if backup_file.stat().st_mtime < cutoff:
            backup_file.unlink()
            removed += 1

    return removed
