"""Mine patterns from findings and record sightings for Rule of Three.

Groups findings by category, normalizes summaries, and clusters similar
findings using Jaccard similarity. Records sightings in the pattern_sightings
table for the v_rule_of_three view.

Usage:
    python scripts/mine_patterns.py
    python scripts/mine_patterns.py --discussion <discussion_id>
    python scripts/mine_patterns.py --dry-run
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"

# ANSI colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Jaccard similarity threshold for clustering
SIMILARITY_THRESHOLD = 0.4

# Stop words for key-phrase extraction
STOP_WORDS = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "shall",
    "can",
    "need",
    "must",
    "ought",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "from",
    "as",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "between",
    "under",
    "over",
    "not",
    "no",
    "nor",
    "but",
    "or",
    "and",
    "if",
    "then",
    "else",
    "when",
    "up",
    "out",
    "off",
    "all",
    "each",
    "every",
    "both",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "only",
    "own",
    "same",
    "so",
    "than",
    "too",
    "very",
    "just",
    "about",
    "also",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its",
}


def _normalize(text: str) -> str:
    """Normalize text for comparison."""
    text = text.lower().strip()
    for ch in "—–-:;,.!?()[]{}\"'":
        text = text.replace(ch, " ")
    return " ".join(text.split())


def _key_phrases(text: str) -> set[str]:
    """Extract key phrases from text."""
    words = set(_normalize(text).split()) - STOP_WORDS
    return {w for w in words if len(w) > 2}


def _jaccard(a: set, b: set) -> float:
    """Compute Jaccard similarity."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _generate_pattern_key(phrases: set[str], category: str) -> str:
    """Generate a stable pattern key from key phrases and category."""
    # Sort phrases for determinism, take top 5 most common
    sorted_phrases = sorted(phrases)[:5]
    key_part = "-".join(sorted_phrases) if sorted_phrases else "unknown"
    return f"{category}:{key_part}"


def mine_patterns(
    discussion_id: str | None = None,
    db_path: Path = DB_PATH,
    dry_run: bool = False,
) -> int:
    """Mine patterns from findings and record sightings.

    Args:
        discussion_id: If provided, only process findings from this discussion.
        db_path: Path to the SQLite database.
        dry_run: If True, report without writing.

    Returns:
        Number of sightings recorded.
    """
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return 0

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")

    # Get findings
    if discussion_id:
        findings = conn.execute(
            """SELECT finding_id, discussion_id, agent, category, summary, created_at
               FROM findings WHERE discussion_id = ?""",
            (discussion_id,),
        ).fetchall()
    else:
        findings = conn.execute(
            """SELECT finding_id, discussion_id, agent, category, summary, created_at
               FROM findings"""
        ).fetchall()

    if not findings:
        print("No findings to mine")
        conn.close()
        return 0

    # Build finding objects with key phrases
    finding_objs = []
    for finding_id, disc_id, agent, category, summary, created_at in findings:
        finding_objs.append(
            {
                "finding_id": finding_id,
                "discussion_id": disc_id,
                "agent": agent,
                "category": category,
                "summary": summary,
                "created_at": created_at,
                "phrases": _key_phrases(summary),
            }
        )

    # Cluster by category first, then by similarity
    by_category: dict[str, list[dict]] = {}
    for f in finding_objs:
        by_category.setdefault(f["category"], []).append(f)

    total_sightings = 0
    pattern_report = []

    for category, cat_findings in by_category.items():
        clusters: list[list[dict]] = []

        for finding in cat_findings:
            matched = False
            for cluster in clusters:
                if _jaccard(finding["phrases"], cluster[0]["phrases"]) >= SIMILARITY_THRESHOLD:
                    cluster.append(finding)
                    matched = True
                    break
            if not matched:
                clusters.append([finding])

        # Record sightings for each cluster
        for cluster in clusters:
            pattern_key = _generate_pattern_key(cluster[0]["phrases"], category)
            disc_count = len(set(f["discussion_id"] for f in cluster))

            pattern_report.append(
                {
                    "pattern_key": pattern_key,
                    "category": category,
                    "count": len(cluster),
                    "discussions": disc_count,
                    "example": cluster[0]["summary"][:80],
                }
            )

            for finding in cluster:
                if not dry_run:
                    # Check for existing sighting to avoid duplicates
                    existing = conn.execute(
                        """SELECT id FROM pattern_sightings
                           WHERE pattern_key = ? AND finding_id = ?""",
                        (pattern_key, finding["finding_id"]),
                    ).fetchone()

                    if not existing:
                        conn.execute(
                            """INSERT INTO pattern_sightings
                               (pattern_key, finding_id, discussion_id, agent,
                                source_type, sighted_at)
                               VALUES (?, ?, ?, ?, 'finding', ?)""",
                            (
                                pattern_key,
                                finding["finding_id"],
                                finding["discussion_id"],
                                finding["agent"],
                                finding["created_at"],
                            ),
                        )
                        total_sightings += 1
                else:
                    total_sightings += 1

    if not dry_run:
        conn.commit()

    # Report
    print(f"\n{BOLD}Pattern Mining Results{RESET}")
    print(f"  Total findings analyzed: {len(finding_objs)}")
    print(f"  Patterns identified: {len(pattern_report)}")
    print(f"  Sightings recorded: {total_sightings}")

    # Show patterns crossing Rule of Three threshold
    multi_disc = [p for p in pattern_report if p["discussions"] >= 3]
    if multi_disc:
        print(f"\n  {GREEN}Patterns crossing Rule of Three (3+ discussions):{RESET}")
        for p in sorted(multi_disc, key=lambda x: -x["discussions"]):
            print(f"    [{p['category']}] {p['example']} ({p['discussions']} discussions)")

    if not dry_run:
        # Query the view for summary
        try:
            r3_rows = conn.execute("SELECT * FROM v_rule_of_three").fetchall()
            if r3_rows:
                print(f"\n  {BOLD}v_rule_of_three view:{RESET}")
                for row in r3_rows:
                    print(f"    {row[0]}: {row[1]} discussions, {row[2]} agents")
        except sqlite3.OperationalError:
            pass

    conn.close()
    return total_sightings


def main() -> None:
    parser = argparse.ArgumentParser(description="Mine patterns from findings")
    parser.add_argument(
        "--discussion",
        help="Only process findings from a specific discussion",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report patterns without writing to database",
    )
    args = parser.parse_args()
    mine_patterns(discussion_id=args.discussion, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
