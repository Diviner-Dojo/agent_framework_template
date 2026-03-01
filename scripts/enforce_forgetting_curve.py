"""Enforce forgetting curve for promoted knowledge.

Checks all promoted artifacts in memory/ for staleness:
- 90 days without reference → flag for review
- 180 days without reference → move to memory/archive/

Usage:
    python scripts/enforce_forgetting_curve.py
    python scripts/enforce_forgetting_curve.py --dry-run
"""

import argparse
import shutil
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).parent.parent
MEMORY_DIR = PROJECT_ROOT / "memory"
ARCHIVE_DIR = MEMORY_DIR / "archive"
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"

# ANSI colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Staleness thresholds
REVIEW_THRESHOLD_DAYS = 90
ARCHIVE_THRESHOLD_DAYS = 180

# Subdirectories to scan (not archive itself)
KNOWLEDGE_DIRS = ["patterns", "decisions", "reflections", "rules", "lessons"]

# Files to skip
SKIP_FILES = {".gitkeep", "adoption-log.md"}


def _get_file_age_days(filepath: Path) -> int:
    """Get file age in days from modification time."""
    mtime = datetime.fromtimestamp(filepath.stat().st_mtime, tz=UTC)
    return (datetime.now(UTC) - mtime).days


def _get_last_referenced(filepath: Path, conn: sqlite3.Connection | None) -> int | None:
    """Get days since last reference from promotion_candidates table.

    Args:
        filepath: Path to the promoted file.
        conn: Database connection, or None if DB not available.

    Returns:
        Days since last reference, or None if no data.
    """
    if conn is None:
        return None

    try:
        row = conn.execute(
            """SELECT last_referenced_at FROM promotion_candidates
               WHERE target_path = ? AND status = 'approved'
               ORDER BY promoted_at DESC LIMIT 1""",
            (str(filepath.relative_to(PROJECT_ROOT)),),
        ).fetchone()

        if row and row[0]:
            ref_date = datetime.fromisoformat(row[0])
            if ref_date.tzinfo is None:
                ref_date = ref_date.replace(tzinfo=UTC)
            return (datetime.now(UTC) - ref_date).days
    except (sqlite3.OperationalError, ValueError):
        pass

    return None


def enforce_forgetting_curve(db_path: Path = DB_PATH, dry_run: bool = False) -> dict:
    """Check promoted knowledge for staleness and take action.

    Args:
        db_path: Path to the SQLite database.
        dry_run: If True, report without moving files.

    Returns:
        Dict with counts of flagged, archived, and healthy artifacts.
    """
    conn = None
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON")

    results = {
        "healthy": [],
        "flagged_for_review": [],
        "archived": [],
        "skipped": [],
    }

    for subdir_name in KNOWLEDGE_DIRS:
        subdir = MEMORY_DIR / subdir_name
        if not subdir.exists():
            continue

        for filepath in subdir.iterdir():
            if filepath.name in SKIP_FILES or filepath.is_dir():
                continue
            if not filepath.is_file():
                continue

            file_age = _get_file_age_days(filepath)
            last_ref_days = _get_last_referenced(filepath, conn)

            # Use the more recent of file modification or last_referenced_at
            effective_age = min(file_age, last_ref_days) if last_ref_days is not None else file_age
            rel_path = filepath.relative_to(PROJECT_ROOT)

            if effective_age >= ARCHIVE_THRESHOLD_DAYS:
                results["archived"].append(
                    {
                        "path": str(rel_path),
                        "age_days": effective_age,
                        "last_ref_days": last_ref_days,
                    }
                )

                if not dry_run:
                    # Move to archive
                    archive_dest = ARCHIVE_DIR / subdir_name
                    archive_dest.mkdir(parents=True, exist_ok=True)
                    dest = archive_dest / filepath.name
                    shutil.move(str(filepath), str(dest))
                    print(f"  {RED}ARCHIVED: {rel_path} ({effective_age} days){RESET}")

                    # Update promotion_candidates status if applicable
                    if conn:
                        try:
                            conn.execute(
                                """UPDATE promotion_candidates
                                   SET status = 'deferred',
                                       human_verdict = 'auto-archived (forgetting curve)'
                                   WHERE target_path = ? AND status = 'approved'""",
                                (str(rel_path),),
                            )
                        except sqlite3.OperationalError:
                            pass

            elif effective_age >= REVIEW_THRESHOLD_DAYS:
                results["flagged_for_review"].append(
                    {
                        "path": str(rel_path),
                        "age_days": effective_age,
                        "last_ref_days": last_ref_days,
                    }
                )

                if not dry_run:
                    # Re-add to promotion_candidates for review
                    if conn:
                        try:
                            timestamp = datetime.now(UTC).isoformat()
                            candidate_id = (
                                f"CAND-stale-{filepath.stem}-"
                                f"{timestamp.replace(':', '').replace('.', '')[:15]}"
                            )
                            conn.execute(
                                """INSERT OR IGNORE INTO promotion_candidates
                                   (candidate_id, candidate_type, source_type,
                                    source_refs, title, summary, evidence_count,
                                    target_path, status, created_at)
                                   VALUES (?, 'pattern', 'finding', '[]',
                                           ?, ?, 1, ?, 'pending', ?)""",
                                (
                                    candidate_id,
                                    f"Stale review: {filepath.name}",
                                    f"Not referenced for {effective_age} days. "
                                    f"Confirm still relevant or archive.",
                                    str(rel_path),
                                    timestamp,
                                ),
                            )
                        except sqlite3.IntegrityError:
                            pass
                print(f"  {YELLOW}REVIEW NEEDED: {rel_path} ({effective_age} days){RESET}")
            else:
                results["healthy"].append(
                    {
                        "path": str(rel_path),
                        "age_days": effective_age,
                    }
                )

    if conn:
        if not dry_run:
            conn.commit()
        conn.close()

    # Report
    prefix = "[DRY RUN] " if dry_run else ""
    print(f"\n{BOLD}{prefix}Forgetting Curve Report{RESET}")
    print(f"  Healthy: {len(results['healthy'])}")
    print(
        f"  Flagged for review (>={REVIEW_THRESHOLD_DAYS}d): {len(results['flagged_for_review'])}"
    )
    print(f"  Archived (>={ARCHIVE_THRESHOLD_DAYS}d): {len(results['archived'])}")

    if results["flagged_for_review"]:
        print(f"\n  {YELLOW}Files needing review:{RESET}")
        for item in results["flagged_for_review"]:
            print(f"    - {item['path']} ({item['age_days']} days)")

    if results["archived"]:
        action = "Would archive" if dry_run else "Archived"
        print(f"\n  {RED}{action}:{RESET}")
        for item in results["archived"]:
            print(f"    - {item['path']} ({item['age_days']} days)")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Enforce forgetting curve for promoted knowledge")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report staleness without moving files",
    )
    args = parser.parse_args()
    enforce_forgetting_curve(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
