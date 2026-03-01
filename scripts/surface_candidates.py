"""Surface promotion candidates from findings and reflections.

Analyzes the findings and reflections tables for recurring patterns
that should be promoted to Layer 3 (curated memory). Inserts candidates
into the promotion_candidates table for human review.

Usage:
    python scripts/surface_candidates.py
    python scripts/surface_candidates.py --discussion <discussion_id>
    python scripts/surface_candidates.py --dry-run
"""

import argparse
import json
import sqlite3
import sys
from datetime import UTC, datetime
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

# Minimum appearances for a finding pattern to become a candidate
MIN_FINDING_APPEARANCES = 2
# Minimum improvement_rule appearances from reflections
MIN_REFLECTION_APPEARANCES = 2


def _normalize_summary(text: str) -> str:
    """Normalize a finding summary for comparison."""
    # Lowercase and strip
    text = text.lower().strip()
    # Remove common punctuation
    for ch in "—–-:;,.!?()[]{}\"'":
        text = text.replace(ch, " ")
    # Collapse whitespace
    return " ".join(text.split())


def _extract_key_phrases(text: str) -> set[str]:
    """Extract key phrases from normalized text for matching."""
    stop_words = {
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
    words = set(_normalize_summary(text).split()) - stop_words
    return {w for w in words if len(w) > 2}


def _jaccard_similarity(set_a: set, set_b: set) -> float:
    """Compute Jaccard similarity between two sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def surface_from_findings(
    conn: sqlite3.Connection, discussion_id: str | None = None
) -> list[dict]:
    """Find recurring findings across discussions.

    Args:
        conn: Database connection.
        discussion_id: If provided, only look at findings from this discussion.

    Returns:
        List of candidate dictionaries.
    """
    candidates = []

    # Get all findings grouped by category
    if discussion_id:
        rows = conn.execute(
            """SELECT finding_id, discussion_id, agent, category, summary
               FROM findings WHERE discussion_id = ?
               ORDER BY category""",
            (discussion_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT finding_id, discussion_id, agent, category, summary
               FROM findings ORDER BY category"""
        ).fetchall()

    if not rows:
        return []

    # Group findings by category
    by_category: dict[str, list[dict]] = {}
    for finding_id, disc_id, agent, category, summary in rows:
        by_category.setdefault(category, []).append(
            {
                "finding_id": finding_id,
                "discussion_id": disc_id,
                "agent": agent,
                "summary": summary,
                "key_phrases": _extract_key_phrases(summary),
            }
        )

    # For each category, find findings that appear across multiple discussions
    for category, findings in by_category.items():
        # Compare each pair for similarity
        clusters: list[list[dict]] = []

        for finding in findings:
            matched = False
            for cluster in clusters:
                # Compare against first finding in cluster as representative
                sim = _jaccard_similarity(finding["key_phrases"], cluster[0]["key_phrases"])
                if sim >= 0.4:
                    cluster.append(finding)
                    matched = True
                    break
            if not matched:
                clusters.append([finding])

        # Surface clusters that span 2+ discussions
        for cluster in clusters:
            disc_ids = set(f["discussion_id"] for f in cluster)
            if len(disc_ids) >= MIN_FINDING_APPEARANCES:
                representative = cluster[0]
                timestamp = datetime.now(UTC).isoformat()
                candidate_id = (
                    f"CAND-{category}-{timestamp.replace(':', '').replace('.', '')[:15]}"
                )

                candidates.append(
                    {
                        "candidate_id": candidate_id,
                        "candidate_type": "pattern",
                        "source_type": "finding",
                        "source_refs": json.dumps([f["finding_id"] for f in cluster]),
                        "title": f"Recurring {category} finding: {representative['summary'][:80]}",
                        "summary": (
                            f"Found in {len(disc_ids)} discussions across {len(cluster)} instances. "
                            f"Category: {category}. "
                            f"Example: {representative['summary'][:200]}"
                        ),
                        "evidence_count": len(disc_ids),
                        "target_path": f"memory/patterns/{category}-findings.md",
                        "created_at": timestamp,
                    }
                )

    return candidates


def surface_from_reflections(conn: sqlite3.Connection) -> list[dict]:
    """Find recurring improvement rules from agent reflections.

    Args:
        conn: Database connection.

    Returns:
        List of candidate dictionaries.
    """
    candidates = []

    rows = conn.execute(
        """SELECT reflection_id, discussion_id, agent, improvement_rule
           FROM reflections
           WHERE improvement_rule IS NOT NULL AND improvement_rule != ''"""
    ).fetchall()

    if not rows:
        return []

    # Cluster similar improvement rules
    rules = []
    for ref_id, disc_id, agent, rule in rows:
        rules.append(
            {
                "reflection_id": ref_id,
                "discussion_id": disc_id,
                "agent": agent,
                "rule": rule,
                "key_phrases": _extract_key_phrases(rule),
            }
        )

    clusters: list[list[dict]] = []
    for rule in rules:
        matched = False
        for cluster in clusters:
            sim = _jaccard_similarity(rule["key_phrases"], cluster[0]["key_phrases"])
            if sim >= 0.4:
                cluster.append(rule)
                matched = True
                break
        if not matched:
            clusters.append([rule])

    for cluster in clusters:
        agents = set(r["agent"] for r in cluster)
        if len(cluster) >= MIN_REFLECTION_APPEARANCES:
            representative = cluster[0]
            timestamp = datetime.now(UTC).isoformat()
            candidate_id = f"CAND-refl-{timestamp.replace(':', '').replace('.', '')[:15]}"

            candidates.append(
                {
                    "candidate_id": candidate_id,
                    "candidate_type": "rule",
                    "source_type": "reflection",
                    "source_refs": json.dumps([r["reflection_id"] for r in cluster]),
                    "title": f"Agent improvement rule ({len(agents)} agents): {representative['rule'][:60]}",
                    "summary": (
                        f"Suggested by {len(agents)} agents across {len(cluster)} reflections. "
                        f"Rule: {representative['rule'][:200]}"
                    ),
                    "evidence_count": len(cluster),
                    "target_path": "memory/rules/",
                    "created_at": timestamp,
                }
            )

    return candidates


def surface_candidates(
    discussion_id: str | None = None,
    db_path: Path = DB_PATH,
    dry_run: bool = False,
) -> list[dict]:
    """Surface promotion candidates and insert into database.

    Args:
        discussion_id: If provided, focus on findings from this discussion.
        db_path: Path to the SQLite database.
        dry_run: If True, report without writing.

    Returns:
        List of all candidates surfaced.
    """
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return []

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")

    candidates = []
    candidates.extend(surface_from_findings(conn, discussion_id))
    candidates.extend(surface_from_reflections(conn))

    if dry_run:
        print(f"\n{BOLD}Promotion Candidates (dry run){RESET}")
        for c in candidates:
            print(f"  [{c['candidate_type'].upper()}] {c['title'][:80]}")
            print(f"    Evidence: {c['evidence_count']} | Target: {c['target_path']}")
        print(f"\n  Total: {len(candidates)} candidates")
        conn.close()
        return candidates

    inserted = 0
    for c in candidates:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO promotion_candidates
                   (candidate_id, candidate_type, source_type, source_refs,
                    title, summary, evidence_count, target_path, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
                (
                    c["candidate_id"],
                    c["candidate_type"],
                    c["source_type"],
                    c["source_refs"],
                    c["title"],
                    c["summary"],
                    c["evidence_count"],
                    c["target_path"],
                    c["created_at"],
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            pass  # Duplicate candidate_id

    conn.commit()
    conn.close()

    print(f"Surfaced {len(candidates)} candidates ({inserted} new)")
    return candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="Surface promotion candidates")
    parser.add_argument(
        "--discussion",
        help="Focus on findings from a specific discussion",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report candidates without writing to database",
    )
    args = parser.parse_args()
    surface_candidates(discussion_id=args.discussion, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
