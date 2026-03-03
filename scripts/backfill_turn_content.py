"""Backfill turns.content_excerpt and turns.tags from events.jsonl.

Populates the content_excerpt and tags columns added by migration
for turns that were ingested before these columns existed.

Usage:
    python scripts/backfill_turn_content.py [--dry-run]
"""

import argparse
import json
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"
DISCUSSIONS_DIR = PROJECT_ROOT / "discussions"


def _find_events_file(discussion_id: str) -> Path | None:
    """Locate the events.jsonl file for a discussion."""
    for date_dir in sorted(DISCUSSIONS_DIR.iterdir(), reverse=True):
        if not date_dir.is_dir() or date_dir.name.startswith("."):
            continue
        candidate = date_dir / discussion_id / "events.jsonl"
        if candidate.exists():
            return candidate
    return None


def backfill_turn_content(dry_run: bool = False) -> int:
    """Populate content_excerpt and tags for turns missing them.

    Args:
        dry_run: If True, report what would be updated without doing it.

    Returns:
        Number of turns updated.
    """
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}. Run scripts/init_db.py first.")
        return 0

    conn = sqlite3.connect(str(DB_PATH))

    # Check if columns exist
    columns = {row[1] for row in conn.execute("PRAGMA table_info(turns)").fetchall()}
    if "content_excerpt" not in columns or "tags" not in columns:
        print("content_excerpt or tags columns not found. Run scripts/init_db.py first.")
        conn.close()
        return 0

    # Get turns missing content_excerpt
    turns_to_update = conn.execute(
        """SELECT id, discussion_id, turn_id
           FROM turns
           WHERE content_excerpt IS NULL"""
    ).fetchall()

    if not turns_to_update:
        print("All turns already have content_excerpt populated.")
        conn.close()
        return 0

    print(f"Found {len(turns_to_update)} turns to backfill")

    # Group by discussion_id for efficient file reading
    by_discussion: dict[str, list[tuple]] = {}
    for row in turns_to_update:
        by_discussion.setdefault(row[1], []).append(row)

    updated = 0
    for disc_id, turns in by_discussion.items():
        events_file = _find_events_file(disc_id)
        if not events_file:
            print(f"  Skipping {disc_id}: events.jsonl not found")
            continue

        # Parse events file into a turn_id -> event mapping
        events_by_turn: dict[int, dict] = {}
        with open(events_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                event = json.loads(line)
                events_by_turn[event.get("turn_id", 0)] = event

        for turn_row in turns:
            db_id, _, turn_id = turn_row
            event = events_by_turn.get(turn_id)
            if not event:
                continue

            content = event.get("content", "")
            excerpt = content[:500] if len(content) > 500 else content
            tags = json.dumps(event.get("tags", []))

            if dry_run:
                print(f"  [DRY RUN] Would update turn {db_id} ({disc_id}:t{turn_id})")
            else:
                conn.execute(
                    "UPDATE turns SET content_excerpt = ?, tags = ? WHERE id = ?",
                    (excerpt, tags, db_id),
                )
            updated += 1

    if not dry_run:
        conn.commit()
    conn.close()
    print(f"\nBackfill complete: {updated} turns {'would be' if dry_run else ''} updated")
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill turn content excerpts and tags")
    parser.add_argument("--dry-run", action="store_true", help="Report without updating")
    args = parser.parse_args()
    backfill_turn_content(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
