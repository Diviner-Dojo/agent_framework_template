"""Enforce forgetting curve for stale memory items.

Scans the `memory/` directory for items that haven't been reviewed
or updated recently:
- 90 days: flag for review
- 180 days: auto-archive to `memory/archive/`

Uses filesystem modification time exclusively. An earlier draft of this
script queried a SQLite `last_referenced_at` column on `promotion_candidates`
that was never part of the canonical schema (`scripts/init_db.py:124`); the
query has been removed rather than backed by fictional columns. A future
`memory_items` table with a real `last_referenced_at` would be the place
to reintroduce reference-tracking; that is out of scope for Phase 0.

Usage:
    python scripts/enforce_forgetting_curve.py [--dry-run] [--review-days 90] [--archive-days 180]
"""

import argparse
import shutil
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
MEMORY_DIR = PROJECT_ROOT / "memory"
ARCHIVE_DIR = MEMORY_DIR / "archive"

# Subdirectories to scan (exclude archive itself)
_SCAN_DIRS = ["decisions", "lessons", "patterns", "reflections", "rules", "bugs"]

# Files to never archive
_PROTECTED_FILES = {"adoption-log.md", "deploy-safety.md", "regression-ledger.md"}

# Files to skip entirely (not memory items)
_SKIP_FILES = {".gitkeep"}


def _file_age_days(filepath: Path) -> int:
    """Get the age of a file in days based on filesystem modification time.

    Args:
        filepath: Absolute path to the file.

    Returns:
        Age in days since the file was last modified.
    """
    now = datetime.now(UTC)
    mtime = datetime.fromtimestamp(filepath.stat().st_mtime, tz=UTC)
    return (now - mtime).days


def enforce_forgetting_curve(
    review_days: int = 90,
    archive_days: int = 180,
    dry_run: bool = False,
    memory_dir: Path | None = None,
) -> dict[str, list[str]]:
    """Scan memory for stale items and flag/archive them.

    Args:
        review_days: Days before flagging for review.
        archive_days: Days before auto-archiving.
        dry_run: If True, report but don't move files.
        memory_dir: Override memory directory (for testing).

    Returns:
        Dict with 'flagged' and 'archived' file lists.
    """
    mem_dir = memory_dir or MEMORY_DIR
    archive_dir = mem_dir / "archive"

    result: dict[str, list[str]] = {"flagged": [], "archived": []}

    if not mem_dir.exists():
        print("Memory directory not found")
        return result

    archive_dir.mkdir(parents=True, exist_ok=True)

    for subdir_name in _SCAN_DIRS:
        subdir = mem_dir / subdir_name
        if not subdir.is_dir():
            continue

        for filepath in subdir.glob("*.md"):
            if filepath.name in _PROTECTED_FILES:
                continue
            if filepath.name in _SKIP_FILES:
                continue

            age = _file_age_days(filepath)

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
