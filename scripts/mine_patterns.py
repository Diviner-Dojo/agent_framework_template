"""Mine patterns from findings by clustering similar issues.

Groups findings by category and uses Jaccard similarity (threshold 0.4)
on tokenized summaries to identify recurring patterns. Records matches
in the `pattern_sightings` table.

Usage:
    python scripts/mine_patterns.py <discussion_id>
    python scripts/mine_patterns.py --all
"""

import argparse
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from pipeline_utils import pattern_hash as _pattern_hash
from pipeline_utils import tokenize as _tokenize

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"

JACCARD_THRESHOLD = 0.4


def _jaccard_similarity(a: set[str], b: set[str]) -> float:
    """Compute Jaccard similarity between two token sets."""
    if not a or not b:
        return 0.0
    intersection = a & b
    union = a | b
    return len(intersection) / len(union)


def mine_patterns(discussion_id: str | None = None) -> int:
    """Mine patterns from findings and record sightings.

    Args:
        discussion_id: Specific discussion to mine, or None for all unprocessed.

    Returns:
        Number of new pattern sightings recorded.
    """
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        return 0

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys=ON")
    now = datetime.now(UTC).isoformat()

    # Get findings to process
    if discussion_id:
        findings = conn.execute(
            "SELECT id, discussion_id, category, summary FROM findings WHERE discussion_id = ?",
            (discussion_id,),
        ).fetchall()
    else:
        # Get all findings not yet associated with a pattern sighting
        findings = conn.execute(
            """SELECT f.id, f.discussion_id, f.category, f.summary
               FROM findings f
               LEFT JOIN pattern_sightings ps
                   ON ps.discussion_id = f.discussion_id AND ps.category = f.category
               WHERE ps.id IS NULL""",
        ).fetchall()

    if not findings:
        print("No findings to process")
        conn.close()
        return 0

    # Group findings by category
    by_category: dict[str, list[tuple]] = {}
    for finding in findings:
        cat = finding[2]
        by_category.setdefault(cat, []).append(finding)

    sighting_count = 0

    for category, cat_findings in by_category.items():
        # Tokenize all summaries in this category
        tokenized = [(f, _tokenize(f[3])) for f in cat_findings]

        # Cluster by Jaccard similarity
        processed: set[int] = set()
        for i, (finding_a, tokens_a) in enumerate(tokenized):
            if finding_a[0] in processed:
                continue

            # This finding starts a cluster
            cluster_summary = finding_a[3]
            p_hash = _pattern_hash(category, cluster_summary)

            # Check if this pattern already exists
            existing = conn.execute(
                "SELECT id FROM pattern_sightings WHERE pattern_hash = ? AND discussion_id = ?",
                (p_hash, finding_a[1]),
            ).fetchone()

            if not existing:
                conn.execute(
                    """INSERT INTO pattern_sightings
                       (pattern_hash, discussion_id, category, summary, source, created_at)
                       VALUES (?, ?, ?, ?, 'discussion', ?)""",
                    (p_hash, finding_a[1], category, cluster_summary, now),
                )
                sighting_count += 1

            processed.add(finding_a[0])

            # Find similar findings in the same category
            for j, (finding_b, tokens_b) in enumerate(tokenized):
                if i == j or finding_b[0] in processed:
                    continue
                if _jaccard_similarity(tokens_a, tokens_b) >= JACCARD_THRESHOLD:
                    existing_b = conn.execute(
                        "SELECT id FROM pattern_sightings WHERE pattern_hash = ? AND discussion_id = ?",
                        (p_hash, finding_b[1]),
                    ).fetchone()
                    if not existing_b:
                        conn.execute(
                            """INSERT INTO pattern_sightings
                               (pattern_hash, discussion_id, category, summary, source, created_at)
                               VALUES (?, ?, ?, ?, 'discussion', ?)""",
                            (p_hash, finding_b[1], category, finding_b[3], now),
                        )
                        sighting_count += 1
                    processed.add(finding_b[0])

    conn.commit()
    conn.close()
    scope = discussion_id or "all unprocessed"
    print(f"Recorded {sighting_count} pattern sightings from {scope}")
    return sighting_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Mine patterns from findings")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("discussion_id", nargs="?", help="Discussion ID to mine")
    group.add_argument("--all", action="store_true", help="Mine all unprocessed findings")
    args = parser.parse_args()
    mine_patterns(None if args.all else args.discussion_id)


if __name__ == "__main__":
    main()
