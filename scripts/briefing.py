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
OUTCOMES = ("clean", "regressed", "reworked")


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


def _ensure_db(db_path: Path) -> None:
    """Create the database and schema if they are not there yet.

    ``sqlite3.connect()`` creates the file, so an unguarded connect on a fresh
    checkout raises "no such table" *and* leaves a 0-byte database behind. Peer
    scripts then see ``DB_PATH.exists()``, skip their own guard, and fail on a
    schema that was never created. Initializing is cheaper than that cascade.

    The import is local so this module stays runnable both as
    ``python scripts/briefing.py`` and as ``scripts.briefing``.
    """
    if db_path.exists():
        return
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from scripts.init_db import init_db
    except ImportError:  # running with scripts/ directly on sys.path
        from init_db import init_db
    init_db(db_path, quiet=True)


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

    _ensure_db(db_path)
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


def record_outcome(
    briefing_id: int,
    outcome: str,
    ref: str | None = None,
    db_path: Path = DB_PATH,
) -> None:
    """Record what happened to the code a briefing covered.

    This is the join ADR-0029 needs and originally lacked: without it a
    deferral and a later regression are two rows that never meet, and the risk
    weights in ``assess_risk.py`` can never be checked against actual regret.

    Args:
        briefing_id: Row id from the ledger.
        outcome: One of clean, regressed, reworked.
        ref: Commit sha, review id, or ledger entry that evidences it.
        db_path: Path to the metrics database.
    """
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {OUTCOMES}, got {outcome!r}")

    _ensure_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute(
            "UPDATE briefings SET outcome = ?, outcome_ref = ?, outcome_at = ? WHERE id = ?",
            (outcome, ref, datetime.now(UTC).isoformat(), briefing_id),
        )
        conn.commit()
    finally:
        conn.close()

    if cur.rowcount == 0:
        print(f"No briefing with id {briefing_id}.")
    else:
        print(f"Briefing {briefing_id} outcome: {outcome}.")


def regret_report(db_path: Path = DB_PATH) -> str:
    """Compare briefing depth and deferral against what happened next.

    The question ADR-0029 said it expected to be wrong about: do the risk
    weights track regret? Answerable only once outcomes accumulate — it will
    say so plainly rather than inventing a signal from three rows.
    """
    _ensure_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            """SELECT depth, status, outcome, COUNT(*)
               FROM briefings WHERE outcome IS NOT NULL
               GROUP BY depth, status, outcome"""
        ).fetchall()
        pending = conn.execute("SELECT COUNT(*) FROM briefings WHERE outcome IS NULL").fetchone()[
            0
        ]
    finally:
        conn.close()

    if not rows:
        return (
            "No briefing outcomes recorded yet — the regret question is not yet "
            f"answerable ({pending} briefing(s) awaiting an outcome).\n"
            "Record one with: briefing.py outcome <id> <clean|regressed|reworked>"
        )

    lines = ["Briefing depth vs what happened next:", ""]
    for depth, status, outcome, n in sorted(rows):
        lines.append(f"  {depth:<9} {status:<10} {outcome:<10} {n}")
    lines.append("")
    lines.append(f"  {pending} briefing(s) still awaiting an outcome.")
    return "\n".join(lines)


def ledger(db_path: Path = DB_PATH, limit: int = 10) -> str:
    """Render the briefing ledger: what you have been taught, and what is owed."""
    _ensure_db(db_path)
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
        lines.append(f"  {marker} #{row['id']} {stamp}  [{row['depth']}] {row['scope']}")
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

    out = sub.add_parser("outcome", help="Record what happened to briefed code")
    out.add_argument("briefing_id", type=int, help="Row id shown in the ledger")
    out.add_argument("outcome", choices=OUTCOMES)
    out.add_argument("--ref", help="Commit sha, review id, or ledger entry")

    sub.add_parser("regret", help="Compare briefing depth against what happened next")

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
    elif args.command == "ledger":
        print(ledger(limit=args.limit))
    elif args.command == "outcome":
        record_outcome(args.briefing_id, args.outcome, ref=args.ref)
    else:
        print(regret_report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
