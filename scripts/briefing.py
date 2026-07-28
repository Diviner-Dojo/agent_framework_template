"""Record and report decision-readiness briefings.

The v3 education gate scored the developer on a Bloom's-taxonomy ladder and
recorded pass/fail. That framing was wrong in two ways: it treated
understanding as an exam, and it gave the framework standing to judge the
person it exists to serve.

v4 records only what actually happened — a briefing was `delivered`, or the
developer chose to `deferred` it. There is no score and no failure state.
Deferring is a legitimate choice; it is written down, not blocked, so the
ledger stays honest without becoming a punishment.

Usage:
    python scripts/briefing.py record --scope src/auth.py --depth standard \\
        --risk 5 --concept "Session tokens are rotated on privilege change"
    python scripts/briefing.py record --scope src/auth.py --depth deep \\
        --risk 6 --deferred --note "shipping a demo, will revisit Monday"
    python scripts/briefing.py ledger
"""

from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"

DEPTHS = ("light", "standard", "deep")


def _current_sha() -> str | None:
    """Return the current HEAD sha, or None outside a repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def record(
    scope: str,
    depth: str,
    risk_score: int,
    deferred: bool = False,
    concept: str | None = None,
    note: str | None = None,
    discussion_id: str | None = None,
    db_path: Path = DB_PATH,
) -> None:
    """Write one briefing outcome to the ledger.

    Args:
        scope: What the briefing covered (paths, or a short description).
        depth: One of light, standard, deep.
        risk_score: Score from assess_risk.py that selected the depth.
        deferred: True if the developer chose to skip it.
        concept: The single idea the developer should now hold.
        note: Free text — their words, or why it was deferred.
        discussion_id: Originating discussion, if any.
        db_path: Path to the metrics database.
    """
    if depth not in DEPTHS:
        raise ValueError(f"depth must be one of {DEPTHS}, got {depth!r}")

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(
            """INSERT INTO briefings
               (scope, depth, risk_score, status, concept, note,
                commit_sha, discussion_id, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                scope,
                depth,
                risk_score,
                "deferred" if deferred else "delivered",
                concept,
                note,
                _current_sha(),
                discussion_id,
                datetime.now(UTC).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    if deferred:
        print(f"Deferred: {scope} ({depth}). Recorded — run /teach when you want it.")
    else:
        print(f"Briefed: {scope} ({depth}).")


def ledger(db_path: Path = DB_PATH, limit: int = 10) -> str:
    """Render the briefing ledger: what you have been taught, and what is owed."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM briefings ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
        deferred = conn.execute(
            "SELECT COUNT(*) FROM briefings WHERE status = 'deferred'"
        ).fetchone()[0]
        delivered = conn.execute(
            "SELECT COUNT(*) FROM briefings WHERE status = 'delivered'"
        ).fetchone()[0]
    finally:
        conn.close()

    lines = [f"Briefings: {delivered} delivered, {deferred} deferred"]
    if deferred:
        lines.append(f"  {deferred} change(s) you haven't been walked through yet. No rush.")
    if not rows:
        lines.append("  (nothing recorded yet)")
        return "\n".join(lines)

    lines.append("")
    for row in rows:
        marker = "·" if row["status"] == "delivered" else "○"
        stamp = row["timestamp"][:10]
        lines.append(f"  {marker} {stamp}  [{row['depth']}] {row['scope']}")
        if row["concept"]:
            lines.append(f"        {row['concept']}")
    return "\n".join(lines)


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Record and report briefings")
    sub = parser.add_subparsers(dest="command", required=True)

    rec = sub.add_parser("record", help="Record a briefing outcome")
    rec.add_argument("--scope", required=True, help="What the briefing covered")
    rec.add_argument("--depth", required=True, choices=DEPTHS)
    rec.add_argument("--risk", type=int, required=True, help="Score from assess_risk.py")
    rec.add_argument("--deferred", action="store_true", help="Developer chose to skip")
    rec.add_argument("--concept", help="The single idea they should now hold")
    rec.add_argument("--note", help="Their words, or why it was deferred")
    rec.add_argument("--discussion-id", help="Originating discussion")

    led = sub.add_parser("ledger", help="Show the briefing ledger")
    led.add_argument("--limit", type=int, default=10)

    args = parser.parse_args()

    if args.command == "record":
        record(
            scope=args.scope,
            depth=args.depth,
            risk_score=args.risk,
            deferred=args.deferred,
            concept=args.concept,
            note=args.note,
            discussion_id=args.discussion_id,
        )
    else:
        print(ledger(limit=args.limit))
    return 0


if __name__ == "__main__":
    sys.exit(main())
