"""Compute agent effectiveness metrics for a discussion.

For each agent in a discussion, computes:
- Findings produced (total from this agent)
- Findings unique (not duplicated by other agents, via Jaccard similarity)
- Findings survived (present in the facilitator synthesis)
- Findings dropped (produced but not in synthesis)
- Confidence average and accuracy

Usage:
    python scripts/compute_agent_effectiveness.py <discussion_id>
    python scripts/compute_agent_effectiveness.py --all
    python scripts/compute_agent_effectiveness.py --dry-run
"""

import argparse
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

# Jaccard similarity threshold for duplicate detection
UNIQUENESS_THRESHOLD = 0.5


def _key_phrases(text: str) -> set[str]:
    """Extract key phrases from text."""
    text = text.lower().strip()
    for ch in "—–-:;,.!?()[]{}\"'":
        text = text.replace(ch, " ")
    words = set(text.split()) - STOP_WORDS
    return {w for w in words if len(w) > 2}


def _jaccard(a: set, b: set) -> float:
    """Compute Jaccard similarity."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def compute_effectiveness(
    discussion_id: str,
    db_path: Path = DB_PATH,
    dry_run: bool = False,
) -> dict[str, dict]:
    """Compute effectiveness metrics for each agent in a discussion.

    Args:
        discussion_id: The discussion to analyze.
        db_path: Path to the SQLite database.
        dry_run: If True, report without writing.

    Returns:
        Dict mapping agent name to effectiveness metrics.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")

    # Get findings by agent for this discussion
    findings = conn.execute(
        """SELECT finding_id, agent, summary, severity
           FROM findings WHERE discussion_id = ?""",
        (discussion_id,),
    ).fetchall()

    if not findings:
        conn.close()
        return {}

    # Get synthesis content (facilitator's synthesis event)
    synthesis_rows = conn.execute(
        """SELECT content_excerpt FROM turns
           WHERE discussion_id = ? AND agent = 'facilitator'
           AND intent = 'synthesis'""",
        (discussion_id,),
    ).fetchall()

    synthesis_text = " ".join(r[0] or "" for r in synthesis_rows).lower()
    synthesis_phrases = _key_phrases(synthesis_text)

    # Get confidence values from turns
    confidence_by_agent: dict[str, list[float]] = {}
    conf_rows = conn.execute(
        """SELECT agent, confidence FROM turns
           WHERE discussion_id = ? AND agent != 'facilitator'""",
        (discussion_id,),
    ).fetchall()
    for agent, conf in conf_rows:
        confidence_by_agent.setdefault(agent, []).append(conf)

    # Group findings by agent
    by_agent: dict[str, list[dict]] = {}
    all_findings_phrases: list[tuple[str, set[str]]] = []

    for finding_id, agent, summary, severity in findings:
        phrases = _key_phrases(summary)
        by_agent.setdefault(agent, []).append(
            {
                "finding_id": finding_id,
                "summary": summary,
                "severity": severity,
                "phrases": phrases,
            }
        )
        all_findings_phrases.append((agent, phrases))

    results = {}
    timestamp = datetime.now(UTC).isoformat()

    for agent, agent_findings in by_agent.items():
        produced = len(agent_findings)

        # Uniqueness: finding not duplicated by another agent
        unique = 0
        for finding in agent_findings:
            is_unique = True
            for other_agent, other_phrases in all_findings_phrases:
                if other_agent == agent:
                    continue
                if _jaccard(finding["phrases"], other_phrases) >= UNIQUENESS_THRESHOLD:
                    is_unique = False
                    break
            if is_unique:
                unique += 1

        # Survival: finding appears in synthesis
        survived = 0
        for finding in agent_findings:
            # Check if key phrases from finding appear in synthesis
            if finding["phrases"] and synthesis_phrases:
                overlap = len(finding["phrases"] & synthesis_phrases)
                # At least 30% of finding phrases in synthesis = survived
                if overlap / len(finding["phrases"]) >= 0.3:
                    survived += 1

        dropped = produced - survived

        # Confidence metrics
        conf_values = confidence_by_agent.get(agent, [])
        conf_avg = sum(conf_values) / len(conf_values) if conf_values else None

        # Confidence accuracy: how well confidence predicted finding survival
        # Higher confidence should correlate with higher survival rate
        survival_rate = survived / produced if produced > 0 else 0.0
        conf_accuracy = 1.0 - abs((conf_avg or 0.8) - survival_rate) if conf_avg else None

        results[agent] = {
            "discussion_id": discussion_id,
            "agent": agent,
            "findings_produced": produced,
            "findings_unique": unique,
            "findings_survived": survived,
            "findings_dropped": dropped,
            "confidence_avg": conf_avg,
            "confidence_accuracy": conf_accuracy,
            "computed_at": timestamp,
        }

    if dry_run:
        print(f"\n{BOLD}Agent Effectiveness (dry run) — {discussion_id}{RESET}")
        for agent, metrics in results.items():
            print(f"  {agent}:")
            print(f"    Produced: {metrics['findings_produced']}")
            print(f"    Unique: {metrics['findings_unique']}")
            print(f"    Survived: {metrics['findings_survived']}")
            print(f"    Dropped: {metrics['findings_dropped']}")
            if metrics["confidence_avg"] is not None:
                print(f"    Confidence avg: {metrics['confidence_avg']:.3f}")
        conn.close()
        return results

    # Write to database
    for agent, metrics in results.items():
        conn.execute(
            """INSERT OR REPLACE INTO agent_effectiveness
               (discussion_id, agent, findings_produced, findings_unique,
                findings_survived, findings_dropped, confidence_avg,
                confidence_accuracy, computed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                metrics["discussion_id"],
                metrics["agent"],
                metrics["findings_produced"],
                metrics["findings_unique"],
                metrics["findings_survived"],
                metrics["findings_dropped"],
                metrics["confidence_avg"],
                metrics["confidence_accuracy"],
                metrics["computed_at"],
            ),
        )

    conn.commit()
    conn.close()

    print(f"Computed effectiveness for {len(results)} agents in {discussion_id}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute agent effectiveness metrics")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("discussion_id", nargs="?", help="Discussion ID")
    group.add_argument("--all", action="store_true", help="Process all discussions")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report without writing to database",
    )
    args = parser.parse_args()

    if args.all:
        conn = sqlite3.connect(str(DB_PATH))
        disc_ids = [
            r[0]
            for r in conn.execute(
                "SELECT discussion_id FROM discussions WHERE status = 'closed'"
            ).fetchall()
        ]
        conn.close()

        for disc_id in disc_ids:
            compute_effectiveness(disc_id, dry_run=args.dry_run)
    else:
        compute_effectiveness(args.discussion_id, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
