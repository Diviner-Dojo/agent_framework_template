"""Ingest events.jsonl into the SQLite turns table.

Usage:
    python scripts/ingest_events.py <discussion_id>

Reads the events.jsonl for the given discussion and inserts all events
into the turns table with SHA-256 content hashes.
"""

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DISCUSSIONS_DIR = PROJECT_ROOT / "discussions"
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"


def find_discussion_dir(discussion_id: str) -> Path:
    """Find the directory for a given discussion ID."""
    for date_dir in sorted(DISCUSSIONS_DIR.iterdir(), reverse=True):
        if not date_dir.is_dir() or date_dir.name.startswith("."):
            continue
        candidate = date_dir / discussion_id
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Discussion directory not found for {discussion_id}")


def ingest_events(discussion_id: str, db_path: Path = DB_PATH) -> int:
    """Read events.jsonl and insert into SQLite turns table.

    Args:
        discussion_id: The discussion to ingest.
        db_path: Path to the SQLite database.

    Returns:
        Number of events ingested.
    """
    disc_dir = find_discussion_dir(discussion_id)
    events_path = disc_dir / "events.jsonl"

    if not events_path.exists():
        raise FileNotFoundError(f"No events.jsonl found at {events_path}")

    events = []
    with open(events_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))

    if not events:
        print(f"No events to ingest for {discussion_id}")
        return 0

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")

    for event in events:
        content_hash = hashlib.sha256(event["content"].encode("utf-8")).hexdigest()

        conn.execute(
            """INSERT OR IGNORE INTO turns
               (discussion_id, turn_id, agent, reply_to, intent,
                timestamp, confidence, content_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event["discussion_id"],
                event["turn_id"],
                event["agent"],
                event.get("reply_to"),
                event["intent"],
                event["timestamp"],
                event["confidence"],
                content_hash,
            ),
        )

    # Update agent_count in discussions table
    agents = set(e["agent"] for e in events)
    conn.execute(
        "UPDATE discussions SET agent_count = ? WHERE discussion_id = ?",
        (len(agents), discussion_id),
    )

    conn.commit()
    conn.close()

    print(f"Ingested {len(events)} events for {discussion_id}")
    return len(events)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest events into SQLite")
    parser.add_argument("discussion_id", help="Discussion ID")
    args = parser.parse_args()
    ingest_events(args.discussion_id)


if __name__ == "__main__":
    main()
