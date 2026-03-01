"""Close and seal a discussion.

Usage:
    python scripts/close_discussion.py <discussion_id>

This script:
1. Generates transcript.md from events.jsonl
2. Ingests events into SQLite
3. Marks the discussion as closed in SQLite
4. Extracts findings into the findings table (Phase 4.1)
4b. Mines patterns and records sightings (Phase 5.1)
5. Surfaces promotion candidates (Phase 4.4)
6. Computes agent effectiveness (Phase 5.2)
7. Sets events.jsonl and transcript.md to read-only (advisory)
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

    # Step 3: Mark discussion as closed in SQLite and compute duration
    if DB_PATH.exists():
        now = datetime.now(UTC).isoformat()
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(
            "UPDATE discussions SET status = 'closed', closed_at = ? WHERE discussion_id = ?",
            (now, discussion_id),
        )
        # Compute duration_minutes from created_at to closed_at
        conn.execute(
            """UPDATE discussions
               SET duration_minutes = ROUND(
                   (julianday(closed_at) - julianday(created_at)) * 24 * 60, 1
               )
               WHERE discussion_id = ?""",
            (discussion_id,),
        )
        conn.commit()
        conn.close()
        print(f"Discussion {discussion_id} marked as closed in SQLite")

    # Step 4: Extract findings (Phase 4.1)
    try:
        from extract_findings import extract_findings

        print(f"Extracting findings for {discussion_id}...")
        extract_findings(discussion_id)
    except Exception as e:
        print(f"Warning: findings extraction failed: {e}")

    # Step 4b: Mine patterns and record sightings (Phase 5.1)
    try:
        from mine_patterns import mine_patterns

        print(f"Mining patterns for {discussion_id}...")
        mine_patterns(discussion_id=discussion_id)
    except Exception as e:
        print(f"Warning: pattern mining failed: {e}")

    # Step 5: Surface promotion candidates (Phase 4.4)
    try:
        from surface_candidates import surface_candidates

        print(f"Surfacing promotion candidates for {discussion_id}...")
        surface_candidates(discussion_id=discussion_id)
    except Exception as e:
        print(f"Warning: candidate surfacing failed: {e}")

    # Step 6: Compute agent effectiveness (Phase 5.2)
    try:
        from compute_agent_effectiveness import compute_effectiveness

        print(f"Computing agent effectiveness for {discussion_id}...")
        compute_effectiveness(discussion_id)
    except Exception as e:
        print(f"Warning: effectiveness computation failed: {e}")

    # Step 7: Set files to read-only (advisory immutability)
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
