"""Backfill content_excerpt and tags columns in the turns table.

One-time migration: reads events.jsonl for each closed discussion and
updates turns rows with searchable content.

Usage:
    python scripts/backfill_turn_content.py
    python scripts/backfill_turn_content.py --dry-run
"""

import argparse
import json
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DISCUSSIONS_DIR = PROJECT_ROOT / "discussions"
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"

# ANSI colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"


def find_discussion_dir(discussion_id: str) -> Path | None:
    """Find the directory for a given discussion ID."""
    for date_dir in sorted(DISCUSSIONS_DIR.iterdir(), reverse=True):
        if not date_dir.is_dir() or date_dir.name.startswith("."):
            continue
        candidate = date_dir / discussion_id
        if candidate.exists():
            return candidate
    return None


def backfill_turn_content(db_path: Path = DB_PATH, dry_run: bool = False) -> int:
    """Backfill content_excerpt and tags for all turns missing them.

    Args:
        db_path: Path to the SQLite database.
        dry_run: If True, report what would be updated without writing.

    Returns:
        Number of turns updated.
    """
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return 0

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")

    # Get all discussions that have turns without content_excerpt
    rows = conn.execute(
        """SELECT DISTINCT discussion_id FROM turns
           WHERE content_excerpt IS NULL"""
    ).fetchall()

    discussion_ids = [r[0] for r in rows]

    if not discussion_ids:
        print(f"{GREEN}All turns already have content_excerpt. Nothing to backfill.{RESET}")
        conn.close()
        return 0

    print(f"Found {len(discussion_ids)} discussions with turns needing backfill")

    total_updated = 0

    for disc_id in discussion_ids:
        disc_dir = find_discussion_dir(disc_id)
        if disc_dir is None:
            print(f"  {YELLOW}Skipping {disc_id}: directory not found{RESET}")
            continue

        events_path = disc_dir / "events.jsonl"
        if not events_path.exists():
            print(f"  {YELLOW}Skipping {disc_id}: no events.jsonl{RESET}")
            continue

        events = {}
        with open(events_path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                event = json.loads(line)
                events[event["turn_id"]] = event

        updated = 0
        for turn_id, event in events.items():
            content_excerpt = event["content"][:500]
            tags_json = json.dumps(event.get("tags", [])) if event.get("tags") else None

            if not dry_run:
                result = conn.execute(
                    """UPDATE turns
                       SET content_excerpt = ?, tags = ?
                       WHERE discussion_id = ? AND turn_id = ?
                       AND content_excerpt IS NULL""",
                    (content_excerpt, tags_json, disc_id, turn_id),
                )
                updated += result.rowcount
            else:
                updated += 1

        total_updated += updated
        print(f"  {disc_id}: {updated} turns {'would be ' if dry_run else ''}updated")

    if not dry_run:
        conn.commit()

    conn.close()

    action = "would update" if dry_run else "updated"
    print(
        f"\n{BOLD}Total: {action} {total_updated} turns across {len(discussion_ids)} discussions{RESET}"
    )
    return total_updated


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill content_excerpt and tags in turns table"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be updated without writing",
    )
    args = parser.parse_args()
    backfill_turn_content(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
