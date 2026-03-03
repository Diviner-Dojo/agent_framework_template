"""Close and seal a discussion.

Usage:
    python scripts/close_discussion.py <discussion_id>

This script:
1. Generates transcript.md from events.jsonl
2. Ingests events into SQLite
3. Marks the discussion as closed in SQLite
4. Sets events.jsonl and transcript.md to read-only (advisory)
"""

import argparse
import sqlite3
import stat
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"

# Import sibling scripts
from generate_transcript import find_discussion_dir, generate_transcript
from ingest_events import ingest_events


def close_discussion(discussion_id: str) -> None:
    """Seal a discussion: generate transcript, ingest to SQLite, mark closed.

    Args:
        discussion_id: The discussion to close.
    """
    disc_dir = find_discussion_dir(discussion_id)

    # Step 1: Generate transcript
    print(f"Generating transcript for {discussion_id}...")
    generate_transcript(discussion_id)

    # Step 2: Ingest events into SQLite
    print(f"Ingesting events for {discussion_id}...")
    ingest_events(discussion_id)

    # Step 3: Mark discussion as closed in SQLite
    if DB_PATH.exists():
        now = datetime.now(UTC).isoformat()
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(
            "UPDATE discussions SET status = 'closed', closed_at = ? WHERE discussion_id = ?",
            (now, discussion_id),
        )
        conn.commit()
        conn.close()
        print(f"Discussion {discussion_id} marked as closed in SQLite")

    # Step 4: Knowledge pipeline amplification (optional — failures don't break closure)
    try:
        from extract_findings import extract_findings as _extract
        from mine_patterns import mine_patterns as _mine

        print(f"Running knowledge pipeline for {discussion_id}...")
        _extract(discussion_id)
        _mine(discussion_id)
    except Exception as exc:
        print(f"Knowledge pipeline skipped (non-fatal): {exc}")

    # Step 5: Set files to read-only (advisory immutability)
    for filename in ["events.jsonl", "transcript.md"]:
        filepath = disc_dir / filename
        if filepath.exists():
            try:
                filepath.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            except OSError:
                # On some systems (Windows) this may not work fully
                pass

    print(f"Discussion {discussion_id} sealed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Close and seal a discussion")
    parser.add_argument("discussion_id", help="Discussion ID")
    args = parser.parse_args()
    close_discussion(args.discussion_id)


if __name__ == "__main__":
    main()
