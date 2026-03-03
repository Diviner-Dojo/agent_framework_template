"""Surface promotion candidates from recurring pattern sightings.

Identifies patterns that appear across multiple discussions and records
them as promotion candidates for human review.

Usage:
    python scripts/surface_candidates.py [--threshold 3]
"""

import argparse
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"


def surface_candidates(threshold: int = 3) -> int:
    """Identify recurring patterns and create promotion candidates.

    Patterns seen in >= threshold distinct discussions become candidates
    for promotion to Layer 3 (curated memory).

    Args:
        threshold: Minimum distinct discussion count to surface a candidate.

    Returns:
        Number of new candidates surfaced.
    """
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        return 0

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys=ON")
    now = datetime.now(UTC).isoformat()

    # Find patterns meeting the threshold
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
    args = parser.parse_args()
    surface_candidates(args.threshold)


if __name__ == "__main__":
    main()
