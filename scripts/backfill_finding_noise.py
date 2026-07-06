"""Backfill is_noise flag and recalibrate severity for existing findings.

Idempotent: only rows where the derived is_noise or severity value differs from
the stored value are touched. A second run issues zero DB writes.

Usage:
    python scripts/backfill_finding_noise.py [--dry-run]
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# Ensure sibling-script imports resolve whether this module is run as a script or
# imported as scripts.backfill_finding_noise (the package root is not scripts/).
sys.path.insert(0, str(Path(__file__).parent))

# Single source of truth — private-symbol cross-imports by design (ADR-0022, C2).
from extract_findings import _classify_severity, _is_verdict_boilerplate

# Use init_db's allowlist-guarded migration path for consistency (ADR-0022).
from init_db import init_db as _init_db

DB_PATH = Path(__file__).parent.parent / "metrics" / "evaluation.db"


def run_backfill(db_path: Path = DB_PATH, *, dry_run: bool = False) -> dict:
    """Backfill is_noise and recalibrate severity for all findings rows.

    Args:
        db_path: Path to the SQLite database.
        dry_run: When True, print histogram without writing any changes.

    Returns:
        Dict with 'total', 'noise_flagged', 'severity_changed', 'db_writes' counts.
    """
    if not db_path.exists():
        print(f"[backfill] Database not found: {db_path}")
        return {"total": 0, "noise_flagged": 0, "severity_changed": 0, "db_writes": 0}

    # Run schema migration through the allowlist-guarded init_db path (per R2.1).
    _init_db(db_path, quiet=True)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")

    rows = conn.execute(
        "SELECT id, summary, raw_excerpt, is_noise, severity FROM findings"
    ).fetchall()

    total = len(rows)
    noise_flagged = 0
    severity_changed = 0
    before_severity: dict[str, int] = {}
    after_severity: dict[str, int] = {}

    updates: list[tuple] = []

    for row_id, summary, raw_excerpt, stored_noise, stored_severity in rows:
        before_severity[stored_severity] = before_severity.get(stored_severity, 0) + 1

        new_noise = 1 if _is_verdict_boilerplate(summary or "") else 0

        # Non-noise rows: recompute severity from raw_excerpt (content proxy) + summary.
        if new_noise:
            new_severity = stored_severity  # Noise rows keep existing severity (irrelevant).
        else:
            new_severity = _classify_severity(raw_excerpt or summary or "", summary or "")

        after_severity[new_severity if not new_noise else "noise"] = (
            after_severity.get(new_severity if not new_noise else "noise", 0) + 1
        )

        if new_noise != stored_noise or new_severity != stored_severity:
            updates.append((new_noise, new_severity, row_id))
            if new_noise and not stored_noise:
                noise_flagged += 1
            if new_severity != stored_severity and not new_noise:
                severity_changed += 1

    print(f"[backfill] Total findings: {total}")
    print(f"[backfill] Before severity: {before_severity}")
    print(f"[backfill] After severity (non-noise): {after_severity}")
    print(
        f"[backfill] Rows to update: {len(updates)}  (noise: {noise_flagged}, severity: {severity_changed})"
    )

    db_writes = 0
    if not dry_run and updates:
        for new_noise, new_severity, row_id in updates:
            conn.execute(
                "UPDATE findings SET is_noise = ?, severity = ? WHERE id = ?",
                (new_noise, new_severity, row_id),
            )
        conn.commit()
        db_writes = len(updates)
        print(f"[backfill] Applied {db_writes} updates.")
    elif dry_run:
        print("[backfill] Dry run — no changes written.")

    conn.close()
    return {
        "total": total,
        "noise_flagged": noise_flagged,
        "severity_changed": severity_changed,
        "db_writes": db_writes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill is_noise and severity for findings")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print histogram without writing changes",
    )
    args = parser.parse_args()
    run_backfill(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
