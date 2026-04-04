"""Enforce forgetting curve for stale memory items.

Scans the `memory/` directory for items that haven't been reviewed
or updated recently:
- 90 days: flag for review
- 180 days: auto-archive to `memory/archive/`

Uses SQLite `last_referenced_at` when available (from promotion_candidates
table), falling back to filesystem mtime when the DB column is NULL or
the database is unavailable.

Usage:
    python scripts/enforce_forgetting_curve.py [--dry-run] [--review-days 90] [--archive-days 180]
"""

import argparse
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
MEMORY_DIR = PROJECT_ROOT / "memory"
ARCHIVE_DIR = MEMORY_DIR / "archive"
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"

# Subdirectories to scan (exclude archive itself)
_SCAN_DIRS = ["decisions", "lessons", "patterns", "reflections", "rules", "bugs"]

# Files to never archive
_PROTECTED_FILES = {"adoption-log.md", "deploy-safety.md", "regression-ledger.md"}

# Files to skip entirely (not memory items)
_SKIP_FILES = {".gitkeep"}


def _get_last_referenced_dates(db_path: Path) -> dict[str, datetime]:
    """Query SQLite for last_referenced_at dates from promotion_candidates.

    Args:
        db_path: Path to the evaluation database.

    Returns:
        Dict mapping relative file paths to their last-referenced datetime.
    """
    if not db_path.exists():
        return {}

    try:
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute(
            "SELECT source_file, last_referenced_at FROM promotion_candidates "
            "WHERE last_referenced_at IS NOT NULL"
        ).fetchall()
        conn.close()
    except (sqlite3.OperationalError, sqlite3.DatabaseError):
        return {}

    result: dict[str, datetime] = {}
    for source_file, last_ref in rows:
        if last_ref:
            try:
                result[source_file] = datetime.fromisoformat(last_ref).replace(tzinfo=UTC)
            except (ValueError, TypeError):
                continue
    return result


def _file_age_days(
    filepath: Path,
    memory_dir: Path,
    ref_dates: dict[str, datetime],
) -> int:
    """Get the age of a file in days.

    Uses last_referenced_at from SQLite if available, otherwise falls back
    to filesystem modification time.

    Args:
        filepath: Absolute path to the file.
        memory_dir: Root memory directory (for computing relative paths).
        ref_dates: Dict of relative paths to last-referenced datetimes.

    Returns:
        Age in days since last reference or modification.
    """
    now = datetime.now(UTC)
    # Use forward slashes for cross-platform consistency with SQLite data
    rel_path = filepath.relative_to(memory_dir).as_posix()

    # Try SQLite last_referenced_at first
    if rel_path in ref_dates:
        return (now - ref_dates[rel_path]).days

    # Fall back to filesystem mtime
    mtime = datetime.fromtimestamp(filepath.stat().st_mtime, tz=UTC)
    return (now - mtime).days


def enforce_forgetting_curve(
    review_days: int = 90,
    archive_days: int = 180,
    dry_run: bool = False,
    memory_dir: Path | None = None,
    db_path: Path | None = None,
) -> dict[str, list[str]]:
    """Scan memory for stale items and flag/archive them.

    Args:
        review_days: Days before flagging for review.
        archive_days: Days before auto-archiving.
        dry_run: If True, report but don't move files.
        memory_dir: Override memory directory (for testing).
        db_path: Override database path (for testing).

    Returns:
        Dict with 'flagged' and 'archived' file lists.
    """
    mem_dir = memory_dir or MEMORY_DIR
    archive_dir = mem_dir / "archive"
    database = db_path or DB_PATH

    result: dict[str, list[str]] = {"flagged": [], "archived": []}

    if not mem_dir.exists():
        print("Memory directory not found")
        return result

    archive_dir.mkdir(parents=True, exist_ok=True)

    # Load reference dates from SQLite
    ref_dates = _get_last_referenced_dates(database)

    for subdir_name in _SCAN_DIRS:
        subdir = mem_dir / subdir_name
        if not subdir.is_dir():
            continue

        for filepath in subdir.glob("*.md"):
            if filepath.name in _PROTECTED_FILES:
                continue
            if filepath.name in _SKIP_FILES:
                continue

            age = _file_age_days(filepath, mem_dir, ref_dates)

            if age >= archive_days:
                rel_path = filepath.relative_to(mem_dir)
                archive_dest = (archive_dir / subdir_name).resolve()
                archive_dest.mkdir(parents=True, exist_ok=True)
                dest = (archive_dest / filepath.name).resolve()

                # Validate destination is within the archive directory
                if not str(dest).startswith(str(archive_dir.resolve())):
                    print(f"Skipping {rel_path}: archive destination escapes boundary")
                    continue

                if dry_run:
                    print(f"[DRY RUN] Would archive: {rel_path} ({age} days old)")
                else:
                    shutil.move(str(filepath), str(dest))
                    print(
                        f"Archived: {rel_path} → archive/{subdir_name}/{filepath.name} ({age} days)"
                    )
                result["archived"].append(str(rel_path))

            elif age >= review_days:
                rel_path = filepath.relative_to(mem_dir)
                print(f"Review needed: {rel_path} ({age} days since last update)")
                result["flagged"].append(str(rel_path))

    # Summary
    print(
        f"\nSummary: {len(result['flagged'])} flagged for review, "
        f"{len(result['archived'])} archived"
    )
    return result


def main() -> None:
    """CLI entrypoint for enforce_forgetting_curve."""
    parser = argparse.ArgumentParser(description="Enforce forgetting curve for memory items")
    parser.add_argument("--dry-run", action="store_true", help="Report without moving files")
    parser.add_argument(
        "--review-days", type=int, default=90, help="Days before review flag (default: 90)"
    )
    parser.add_argument(
        "--archive-days", type=int, default=180, help="Days before auto-archive (default: 180)"
    )
    args = parser.parse_args()
    enforce_forgetting_curve(
        review_days=args.review_days,
        archive_days=args.archive_days,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
