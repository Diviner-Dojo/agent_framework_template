"""Compute per-agent effectiveness metrics.

Tracks uniqueness ratio, calibration, and contribution for each agent
across discussions, recording results in the `agent_effectiveness` table.

Usage:
    python scripts/compute_agent_effectiveness.py <discussion_id>
    python scripts/compute_agent_effectiveness.py --all
"""

import argparse
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"


def compute_agent_effectiveness(discussion_id: str | None = None) -> int:
    """Compute effectiveness metrics for agents in a discussion.

    For each agent, calculates:
    - findings_unique: Findings only this agent raised
    - findings_duplicate: Findings also raised by another agent
    - findings_false_positive: Count from protocol_yield (if available)
    - confidence_avg: Mean self-assessed confidence
    - confidence_calibration: |avg_confidence - actual_accuracy| (lower is better)

    Args:
        discussion_id: Specific discussion, or None for all unprocessed.

    Returns:
        Number of agent effectiveness records created.
    """
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        return 0

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys=ON")
    now = datetime.now(UTC).isoformat()

    # Get discussions to process
    if discussion_id:
        discussions = [(discussion_id,)]
    else:
        discussions = conn.execute(
            """SELECT DISTINCT d.discussion_id
               FROM discussions d
               LEFT JOIN agent_effectiveness ae ON ae.discussion_id = d.discussion_id
               WHERE d.status = 'closed' AND ae.id IS NULL"""
        ).fetchall()

    record_count = 0

    for (disc_id,) in discussions:
        # Get findings per agent for this discussion
        agent_findings = conn.execute(
            """SELECT agent, category, COUNT(*) as count
               FROM findings
               WHERE discussion_id = ?
               GROUP BY agent, category""",
            (disc_id,),
        ).fetchall()

        if not agent_findings:
            continue

        # Build per-agent category sets
        agent_categories: dict[str, set[str]] = {}
        agent_finding_counts: dict[str, int] = {}
        for agent, category, count in agent_findings:
            agent_categories.setdefault(agent, set()).add(category)
            agent_finding_counts[agent] = agent_finding_counts.get(agent, 0) + count

        # Get confidence data from turns
        agent_confidences: dict[str, list[float]] = {}
        turns = conn.execute(
            "SELECT agent, confidence FROM turns WHERE discussion_id = ?",
            (disc_id,),
        ).fetchall()
        for agent, confidence in turns:
            agent_confidences.setdefault(agent, []).append(confidence)

        # Compute per-agent metrics
        all_categories = set()
        for cats in agent_categories.values():
            all_categories |= cats

        for agent, categories in agent_categories.items():
            # Categories only this agent found
            other_categories = set()
            for other_agent, other_cats in agent_categories.items():
                if other_agent != agent:
                    other_categories |= other_cats

            unique_cats = categories - other_categories
            duplicate_cats = categories & other_categories

            findings_unique = sum(
                1 for a, c, cnt in agent_findings if a == agent and c in unique_cats
            )
            findings_duplicate = sum(
                1 for a, c, cnt in agent_findings if a == agent and c in duplicate_cats
            )

            # Confidence metrics
            confidences = agent_confidences.get(agent, [])
            confidence_avg = sum(confidences) / len(confidences) if confidences else None

            # Calibration: how close is stated confidence to actual hit rate
            # Approximation: unique/(unique+duplicate) as "accuracy"
            total = findings_unique + findings_duplicate
            if total > 0 and confidence_avg is not None:
                actual_accuracy = findings_unique / total
                calibration = abs(confidence_avg - actual_accuracy)
            else:
                calibration = None

            # Check for existing record
            existing = conn.execute(
                "SELECT id FROM agent_effectiveness WHERE agent = ? AND discussion_id = ?",
                (agent, disc_id),
            ).fetchone()

            if not existing:
                conn.execute(
                    """INSERT INTO agent_effectiveness
                       (agent, discussion_id, findings_unique, findings_duplicate,
                        findings_false_positive, confidence_avg, confidence_calibration, computed_at)
                       VALUES (?, ?, ?, ?, 0, ?, ?, ?)""",
                    (
                        agent,
                        disc_id,
                        findings_unique,
                        findings_duplicate,
                        confidence_avg,
                        calibration,
                        now,
                    ),
                )
                record_count += 1

    conn.commit()
    conn.close()
    scope = discussion_id or "all unprocessed"
    print(f"Computed effectiveness for {record_count} agent-discussion pairs from {scope}")
    return record_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute agent effectiveness metrics")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("discussion_id", nargs="?", help="Discussion ID")
    group.add_argument("--all", action="store_true", help="Process all unprocessed discussions")
    args = parser.parse_args()
    compute_agent_effectiveness(None if args.all else args.discussion_id)


if __name__ == "__main__":
    main()
