"""Create a new discussion directory with the standard ID format.

Usage:
    python scripts/create_discussion.py <slug> [--risk low|medium|high|critical] [--mode ensemble|yes-and|structured-dialogue|dialectic|adversarial]

Outputs the discussion ID to stdout for use by other scripts.
"""

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DISCUSSIONS_DIR = PROJECT_ROOT / "discussions"
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"


def create_discussion(
    slug: str,
    risk_level: str = "medium",
    collaboration_mode: str = "structured-dialogue",
    exploration_intensity: str = "medium",
) -> str:
    """Create a new discussion directory and register it in SQLite.

    Args:
        slug: Short descriptive slug for the discussion.
        risk_level: low, medium, high, or critical.
        collaboration_mode: ensemble, yes-and, structured-dialogue, dialectic, or adversarial.
        exploration_intensity: low, medium, or high.

    Returns:
        The discussion ID string.
    """
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%Y%m%d-%H%M%S")
    discussion_id = f"DISC-{time_str}-{slug}"

    # Create directory structure
    disc_dir = DISCUSSIONS_DIR / date_str / discussion_id
    disc_dir.mkdir(parents=True, exist_ok=True)
    (disc_dir / "artifacts").mkdir(exist_ok=True)

    # Initialize empty events.jsonl
    (disc_dir / "events.jsonl").touch()

    # Register in SQLite
    if DB_PATH.exists():
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(
            """INSERT INTO discussions
               (discussion_id, created_at, risk_level, collaboration_mode,
                exploration_intensity, status, agent_count)
               VALUES (?, ?, ?, ?, ?, 'open', 0)""",
            (discussion_id, now.isoformat(), risk_level,
             collaboration_mode, exploration_intensity),
        )
        conn.commit()
        conn.close()

    print(discussion_id)
    return discussion_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a new discussion directory")
    parser.add_argument("slug", help="Short descriptive slug (e.g., 'auth-refactor')")
    parser.add_argument("--risk", default="medium",
                        choices=["low", "medium", "high", "critical"])
    parser.add_argument("--mode", default="structured-dialogue",
                        choices=["ensemble", "yes-and", "structured-dialogue",
                                 "dialectic", "adversarial"])
    parser.add_argument("--intensity", default="medium",
                        choices=["low", "medium", "high"])
    args = parser.parse_args()

    create_discussion(args.slug, args.risk, args.mode, args.intensity)


if __name__ == "__main__":
    main()
