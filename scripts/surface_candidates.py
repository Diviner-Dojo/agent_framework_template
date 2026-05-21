"""Surface promotion candidates from recurring pattern sightings.

Identifies patterns that appear across multiple discussions and records
them as promotion candidates for human review.

Usage:
    python scripts/surface_candidates.py [--threshold 3]
    python scripts/surface_candidates.py --discussion-id <id> [--threshold 3]
"""

import argparse
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"


def surface_candidates(threshold: int = 3, discussion_id: str | None = None) -> int:
    """Identify recurring patterns and create promotion candidates.

    Patterns seen in >= threshold distinct discussions become candidates
    for promotion to Layer 3 (curated memory).

    When ``discussion_id`` is provided, Rule-of-Three counting always uses
    the full ``pattern_sightings`` table (so cross-discussion accumulation
    is preserved), but only rows whose ``pattern_hash`` has at least one
    sighting in the closing discussion are emitted or updated. This is the
    auto-invoke contract from ``close_discussion.py``: a closure should
    refresh only the patterns it could possibly have changed. Counting is
    always global; scoping is applied at the emission step, never at the
    counting step.

    Args:
        threshold: Minimum distinct discussion count to surface a candidate.
        discussion_id: When set, restrict emission/update to patterns
            sighted in this discussion. When None, retain project-wide
            behaviour (the manual ``--all`` CLI path).

    Returns:
        Number of new candidates surfaced.
    """
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        return 0

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys=ON")
    now = datetime.now(UTC).isoformat()

    # Find patterns meeting the threshold. Rule-of-Three counting always
    # uses the full pattern_sightings table — scoping is applied at the
    # emission step below, never at the counting step.
    if discussion_id is None:
        recurring = conn.execute(
            """SELECT
                   pattern_hash,
                   category,
                   summary,
                   COUNT(DISTINCT discussion_id) as disc_count,
                   MIN(created_at) as first_seen,
                   MAX(created_at) as last_seen,
                   GROUP_CONCAT(DISTINCT discussion_id) as discussion_ids
               FROM pattern_sightings
               GROUP BY pattern_hash
               HAVING COUNT(DISTINCT discussion_id) >= ?
               ORDER BY disc_count DESC""",
            (threshold,),
        ).fetchall()
    else:
        recurring = conn.execute(
            """SELECT
                   pattern_hash,
                   category,
                   summary,
                   COUNT(DISTINCT discussion_id) as disc_count,
                   MIN(created_at) as first_seen,
                   MAX(created_at) as last_seen,
                   GROUP_CONCAT(DISTINCT discussion_id) as discussion_ids
               FROM pattern_sightings
               WHERE pattern_hash IN (
                   SELECT DISTINCT pattern_hash
                   FROM pattern_sightings
                   WHERE discussion_id = ?
               )
               GROUP BY pattern_hash
               HAVING COUNT(DISTINCT discussion_id) >= ?
               ORDER BY disc_count DESC""",
            (discussion_id, threshold),
        ).fetchall()

    if not recurring:
        print(f"No patterns found with >= {threshold} sightings")
        conn.close()
        return 0

    new_count = 0
    for row in recurring:
        p_hash, category, summary, disc_count, first_seen, last_seen, disc_ids = row

        # Check if already a candidate
        existing = conn.execute(
            "SELECT id FROM promotion_candidates WHERE finding_pattern = ?",
            (p_hash,),
        ).fetchone()

        if existing:
            # Update sighting count and last_seen
            conn.execute(
                """UPDATE promotion_candidates
                   SET sighting_count = ?, last_seen = ?, evidence_ids = ?
                   WHERE finding_pattern = ?""",
                (disc_count, last_seen, json.dumps(disc_ids.split(",")), p_hash),
            )
        else:
            conn.execute(
                """INSERT INTO promotion_candidates
                   (finding_pattern, category, sighting_count, first_seen, last_seen, evidence_ids)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    p_hash,
                    category,
                    disc_count,
                    first_seen,
                    last_seen,
                    json.dumps(disc_ids.split(",")),
                ),
            )
            new_count += 1

    conn.commit()
    conn.close()
    print(
        f"Surfaced {new_count} new promotion candidates ({len(recurring)} total recurring patterns)"
    )
    return new_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Surface promotion candidates from patterns")
    parser.add_argument(
        "--threshold",
        type=int,
        default=3,
        help="Minimum discussion count to surface (default: 3)",
    )
    parser.add_argument(
        "--discussion-id",
        default=None,
        help=(
            "Restrict emission/update to patterns sighted in this discussion "
            "(default: project-wide)"
        ),
    )
    args = parser.parse_args()
    surface_candidates(args.threshold, discussion_id=args.discussion_id)


if __name__ == "__main__":
    main()
