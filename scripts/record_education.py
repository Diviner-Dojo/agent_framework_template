"""Record education gate results into the SQLite education_results table.

Usage:
    python scripts/record_education.py <session_id> <discussion_id> <bloom_level> \
        <question_type> <score> <passed>

Example:
    python scripts/record_education.py QUIZ-20260218-143000 \
        DISC-20260218-140000-auth understand walkthrough 0.85 true
"""

import argparse
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"

# Single source of truth for the education_results enums. These mirror the
# CHECK constraints in scripts/init_db.py and are imported by other tooling
# (e.g. scripts/education/ingest_walkthrough_session.py) so enum whitelists are
# never redefined. Keep in sync with the DDL.
BLOOM_LEVELS = ("remember", "understand", "apply", "analyze", "evaluate", "create")
QUESTION_TYPES = ("recall", "walkthrough", "debug-scenario", "change-impact", "explain-back")


def record_education(
    session_id: str,
    discussion_id: str,
    bloom_level: str,
    question_type: str,
    score: float,
    passed: bool,
    db_path: Path = DB_PATH,
) -> None:
    """Record an education result in SQLite.

    Args:
        session_id: Education session identifier.
        discussion_id: The discussion or PR that triggered the gate.
        bloom_level: remember, understand, apply, analyze, evaluate, or create.
        question_type: recall, walkthrough, debug-scenario, change-impact, or explain-back.
        score: 0-1 score.
        passed: Whether the threshold was met.
        db_path: Path to the SQLite database.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        """INSERT INTO education_results
           (session_id, discussion_id, bloom_level, question_type,
            score, passed, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            session_id,
            discussion_id,
            bloom_level,
            question_type,
            score,
            passed,
            datetime.now(UTC).isoformat(),
        ),
    )
    conn.commit()
    conn.close()

    status = "PASSED" if passed else "FAILED"
    print(f"Education result recorded: {bloom_level}/{question_type} = {score:.2f} ({status})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Record education gate results")
    parser.add_argument("session_id", help="Education session ID")
    parser.add_argument("discussion_id", help="Discussion ID that triggered the gate")
    parser.add_argument("bloom_level", choices=list(BLOOM_LEVELS))
    parser.add_argument("question_type", choices=list(QUESTION_TYPES))
    parser.add_argument("score", type=float, help="Score 0-1")
    parser.add_argument("passed", help="true or false")
    args = parser.parse_args()

    passed = args.passed.lower() in ("true", "1", "yes")
    record_education(
        args.session_id,
        args.discussion_id,
        args.bloom_level,
        args.question_type,
        args.score,
        passed,
    )


if __name__ == "__main__":
    main()
