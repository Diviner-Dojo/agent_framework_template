"""Record protocol yield metrics into the protocol_yield table.

Usage:
    python scripts/record_yield.py <discussion_id> <protocol_type> <outcome> \
        [--blocking N] [--advisory N] [--false-positive N] [--turns N]

Example:
    python scripts/record_yield.py DISC-20260222-120000-review-auth review approve \
        --blocking 2 --advisory 5 --turns 8
"""

import argparse
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "metrics" / "evaluation.db"

VALID_PROTOCOL_TYPES = ("review", "checkpoint", "education_gate", "quality_gate", "retro")
VALID_OUTCOMES = (
    "approve",
    "approve-with-changes",
    "request-changes",
    "reject",
    "pass",
    "fail",
    "revise-resolved",
    "revise-unresolved",
)


def record_yield(
    discussion_id: str,
    protocol_type: str,
    outcome: str,
    findings_blocking: int = 0,
    findings_advisory: int = 0,
    findings_false_positive: int = 0,
    agent_turns_used: int = 0,
) -> None:
    """Insert a protocol yield record into SQLite."""
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}. Run scripts/init_db.py first.")
        raise SystemExit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys=ON")

    # Check for existing record to prevent duplicate recording
    existing = conn.execute(
        "SELECT id FROM protocol_yield WHERE discussion_id = ? AND protocol_type = ?",
        (discussion_id, protocol_type),
    ).fetchone()
    if existing:
        print(
            f"WARNING: Yield already recorded for {discussion_id} / {protocol_type} (row {existing[0]}). Skipping duplicate."
        )
        conn.close()
        return

    conn.execute(
        """INSERT INTO protocol_yield
           (discussion_id, protocol_type, findings_blocking, findings_advisory,
            findings_false_positive, agent_turns_used, outcome, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            discussion_id,
            protocol_type,
            findings_blocking,
            findings_advisory,
            findings_false_positive,
            agent_turns_used,
            outcome,
            datetime.now(UTC).isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    print(
        f"Recorded yield: {protocol_type} -> {outcome} (blocking={findings_blocking}, advisory={findings_advisory})"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Record protocol yield metrics")
    parser.add_argument("discussion_id", help="Discussion ID")
    parser.add_argument("protocol_type", choices=VALID_PROTOCOL_TYPES)
    parser.add_argument("outcome", choices=VALID_OUTCOMES)
    parser.add_argument("--blocking", type=int, default=0, help="Blocking findings count")
    parser.add_argument("--advisory", type=int, default=0, help="Advisory findings count")
    parser.add_argument("--false-positive", type=int, default=0, help="False positive count")
    parser.add_argument("--turns", type=int, default=0, help="Agent turns used")
    args = parser.parse_args()

    record_yield(
        args.discussion_id,
        args.protocol_type,
        args.outcome,
        args.blocking,
        args.advisory,
        args.false_positive,
        args.turns,
    )


if __name__ == "__main__":
    main()
