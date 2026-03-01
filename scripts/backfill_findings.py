"""Backfill findings for all existing closed discussions.

One-time migration: runs extract_findings for every closed discussion
that has events.jsonl but no entries in the findings table.

Usage:
    python scripts/backfill_findings.py
    python scripts/backfill_findings.py --dry-run
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).parent.parent
DISCUSSIONS_DIR = PROJECT_ROOT / "discussions"
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"

# ANSI colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Import sibling
from extract_findings import extract_findings


def backfill_findings(db_path: Path = DB_PATH, dry_run: bool = False) -> dict:
    """Backfill findings for all closed discussions.

    Args:
        db_path: Path to the SQLite database.
        dry_run: If True, report counts without writing.

    Returns:
        Dict with total_discussions, total_findings, skipped counts.
    """
    if not db_path.exists():
        print(f"{RED}Database not found: {db_path}{RESET}")
        return {"total_discussions": 0, "total_findings": 0, "skipped": 0}

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")

    # Get all closed discussions
    rows = conn.execute(
        "SELECT discussion_id FROM discussions WHERE status = 'closed' ORDER BY created_at"
    ).fetchall()

    # Get discussions that already have findings
    existing = set(
        r[0] for r in conn.execute("SELECT DISTINCT discussion_id FROM findings").fetchall()
    )

    conn.close()

    discussion_ids = [r[0] for r in rows]
    to_process = [d for d in discussion_ids if d not in existing]

    print(f"{BOLD}Findings Backfill{RESET}")
    print(f"  Total closed discussions: {len(discussion_ids)}")
    print(f"  Already have findings: {len(existing)}")
    print(f"  To process: {len(to_process)}")
    print()

    total_findings = 0
    skipped = 0
    processed = 0

    for disc_id in to_process:
        try:
            findings = extract_findings(disc_id, db_path=db_path, dry_run=dry_run)
            count = len(findings)
            total_findings += count
            processed += 1
        except FileNotFoundError:
            print(f"  {YELLOW}Skipping {disc_id}: directory/events not found{RESET}")
            skipped += 1
        except Exception as e:
            print(f"  {RED}Error processing {disc_id}: {e}{RESET}")
            skipped += 1

    print(f"\n{BOLD}Backfill Summary{RESET}")
    print(f"  Processed: {processed} discussions")
    print(f"  Findings extracted: {total_findings}")
    print(f"  Skipped: {skipped}")

    return {
        "total_discussions": processed,
        "total_findings": total_findings,
        "skipped": skipped,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill findings for all closed discussions")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report findings counts without writing to database",
    )
    args = parser.parse_args()
    backfill_findings(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
