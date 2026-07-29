"""Close and seal a discussion.

Usage:
    python scripts/close_discussion.py <discussion_id>

This script:
1. Generates transcript.md from events.jsonl
2. Ingests events into SQLite
3. Marks the discussion as closed in SQLite (with duration_minutes)
4. Rolls up per-turn token counts into discussion totals
5. Extracts findings into the findings table
6. Mines patterns and records sightings
7. Surfaces promotion candidates
8. Computes agent effectiveness
9. Sets events.jsonl and transcript.md to read-only (advisory)
"""

import argparse
import sqlite3
import stat
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"

YELLOW = "\033[93m"
RESET = "\033[0m"

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

    # Step 3b: Roll up per-turn token counts into discussion totals.
    # Skipped when no turn carries token data — the JSONL ingester
    # (scripts/ingest_token_usage.py) is the authoritative path and writes
    # discussions.total_* directly. See ADR-0013.
    try:
        if DB_PATH.exists():
            conn = sqlite3.connect(str(DB_PATH))
            conn.execute("PRAGMA foreign_keys=ON")
            has_turn_tokens = conn.execute(
                """SELECT 1 FROM turns
                   WHERE discussion_id = ?
                       AND (tokens_in IS NOT NULL OR tokens_out IS NOT NULL
                            OR cache_read_tokens IS NOT NULL OR cache_create_tokens IS NOT NULL)
                   LIMIT 1""",
                (discussion_id,),
            ).fetchone()
            if has_turn_tokens:
                conn.execute(
                    """UPDATE discussions
                       SET total_tokens_in = (
                               SELECT SUM(tokens_in) FROM turns
                               WHERE discussion_id = ? AND tokens_in IS NOT NULL
                           ),
                           total_tokens_out = (
                               SELECT SUM(tokens_out) FROM turns
                               WHERE discussion_id = ? AND tokens_out IS NOT NULL
                           ),
                           total_cache_tokens = (
                               SELECT SUM(
                                   COALESCE(cache_read_tokens, 0) + COALESCE(cache_create_tokens, 0)
                               )
                               FROM turns
                               WHERE discussion_id = ?
                                   AND (cache_read_tokens IS NOT NULL OR cache_create_tokens IS NOT NULL)
                           )
                       WHERE discussion_id = ?""",
                    (discussion_id, discussion_id, discussion_id, discussion_id),
                )
                conn.commit()
                print(f"Token rollup completed for {discussion_id}")
            else:
                print(
                    f"Token rollup skipped for {discussion_id} (no per-turn token data recorded)"
                )
            conn.close()
    except Exception as e:
        print(f"Warning: token rollup failed (non-fatal): {e}")

    # Step 4: Extract findings
    try:
        from extract_findings import extract_findings

        print(f"Extracting findings for {discussion_id}...")
        extract_findings(discussion_id)
    except Exception as e:
        print(f"Warning: findings extraction failed (non-fatal): {e}")

    # Step 5: Mine patterns and record sightings
    try:
        from mine_patterns import mine_patterns

        print(f"Mining patterns for {discussion_id}...")
        mine_patterns(discussion_id=discussion_id)
    except Exception as e:
        print(f"Warning: pattern mining failed (non-fatal): {e}")

    # Step 6: Surface promotion candidates
    try:
        from surface_candidates import surface_candidates

        print(f"Surfacing promotion candidates for {discussion_id}...")
        surface_candidates(discussion_id=discussion_id)
    except Exception as e:
        print(f"Warning: candidate surfacing failed (non-fatal): {e}")

    # Step 7: Compute agent effectiveness
    try:
        from compute_agent_effectiveness import compute_agent_effectiveness

        print(f"Computing agent effectiveness for {discussion_id}...")
        compute_agent_effectiveness(discussion_id)
    except Exception as e:
        print(f"Warning: effectiveness computation failed (non-fatal): {e}")

    # Step 8: Check for pending promotion candidates and notify
    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(str(DB_PATH))
            row = conn.execute(
                "SELECT COUNT(*) FROM promotion_candidates WHERE promoted = 0"
            ).fetchone()
            pending_count = row[0] if row else 0
            conn.close()
            if pending_count > 0:
                print(
                    f"\n{YELLOW}NOTE:{RESET} {pending_count} promotion candidate(s) "
                    f"awaiting review. Run /promote to review them."
                )
        except (sqlite3.OperationalError, Exception):
            pass  # Table may not exist yet

    # Step 9: Set files to read-only (advisory immutability)
    for filename in ["events.jsonl", "transcript.md"]:
        filepath = disc_dir / filename
        if filepath.exists():
            try:
                filepath.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            except OSError:
                # On some systems (Windows) this may not work fully
                pass

    # Step 10: Send push notification
    try:
        from notify import send_notification

        send_notification(
            f"Discussion {discussion_id} closed and sealed.",
            title="Discussion Closed",
            tags="white_check_mark",
        )
    except Exception:
        pass  # Best-effort — never block on notification failure

    print(f"Discussion {discussion_id} sealed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Close and seal a discussion")
    parser.add_argument("discussion_id", help="Discussion ID")
    args = parser.parse_args()
    close_discussion(args.discussion_id)


if __name__ == "__main__":
    main()
