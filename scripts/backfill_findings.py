"""Retroactively extract findings from historical discussions.

Scans all closed discussions that don't yet have findings in the database
and runs the extraction pipeline on them.

Usage:
    python scripts/backfill_findings.py [--dry-run]
"""

import argparse
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"
DISCUSSIONS_DIR = PROJECT_ROOT / "discussions"


def backfill_findings(dry_run: bool = False) -> int:
    """Extract findings from all historical discussions not yet processed.

    Args:
        dry_run: If True, report what would be processed without doing it.

    Returns:
        Number of discussions processed.
    """
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}. Run scripts/init_db.py first.")
        return 0

    conn = sqlite3.connect(str(DB_PATH))

    # Get discussions that have been ingested but don't have findings yet
    try:
        processed_ids = {
            row[0]
            for row in conn.execute("SELECT DISTINCT discussion_id FROM findings").fetchall()
        }
    except sqlite3.OperationalError:
        print("findings table not found. Run scripts/init_db.py first.")
        conn.close()
        return 0

    all_disc_ids = {
        row[0]
        for row in conn.execute(
            "SELECT discussion_id FROM discussions WHERE status = 'closed'"
        ).fetchall()
    }
    conn.close()

    unprocessed = all_disc_ids - processed_ids
    if not unprocessed:
        print("All discussions already have findings extracted.")
        return 0

    print(f"Found {len(unprocessed)} discussions to backfill")

    if dry_run:
        for disc_id in sorted(unprocessed):
            print(f"  [DRY RUN] Would process: {disc_id}")
        return 0

    # Import extraction function
    from extract_findings import extract_findings
    from mine_patterns import mine_patterns

    processed = 0
    for disc_id in sorted(unprocessed):
        try:
            count = extract_findings(disc_id)
            if count > 0:
                mine_patterns(disc_id)
            processed += 1
        except FileNotFoundError:
            print(f"  Skipping {disc_id}: discussion directory not found on disk")
        except Exception as exc:
            print(f"  Error processing {disc_id}: {exc}")

    print(f"\nBackfill complete: {processed}/{len(unprocessed)} discussions processed")
    return processed


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill findings from historical discussions")
    parser.add_argument("--dry-run", action="store_true", help="Report without processing")
    args = parser.parse_args()
    backfill_findings(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
