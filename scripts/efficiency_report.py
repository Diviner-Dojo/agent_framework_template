"""Print a text efficiency report over captured token telemetry.

Reads ``metrics/evaluation.db`` and produces sliced views of token spend
and blocking-finding yield. The primary efficiency ratio is
``blocking findings per 1K output tokens`` — high values mean a workflow
is producing more independently-found blocking issues per unit of cost.

Cost in dollars is intentionally NOT computed. The aggregated columns
mix turns across multiple model tiers (facilitator at opus, specialists
mostly at sonnet, etc.), so any single per-token rate would fabricate
precision the data doesn't have. ``config/model_pricing.yaml`` is the
reference table for manual cost estimation when a single-tier
discussion is being analyzed.

Usage:
    python scripts/efficiency_report.py
    python scripts/efficiency_report.py --since 2026-05-01
    python scripts/efficiency_report.py --top 20
"""

from __future__ import annotations

import argparse
import sqlite3
from collections.abc import Sequence
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"


def _format_table(rows: Sequence[Sequence[object]], headers: Sequence[str]) -> str:
    """Render rows as a fixed-width text table. Right-justify numeric cells."""
    cols = len(headers)
    str_rows: list[list[str]] = [list(headers)]
    for row in rows:
        str_rows.append(["" if v is None else str(v) for v in row])
    widths = [max(len(r[c]) for r in str_rows) for c in range(cols)]
    lines: list[str] = []
    for i, row in enumerate(str_rows):
        cells = []
        for c, cell in enumerate(row):
            try:
                float(cell)
                cells.append(cell.rjust(widths[c]))
            except (ValueError, TypeError):
                cells.append(cell.ljust(widths[c]))
        lines.append("  ".join(cells))
        if i == 0:
            lines.append("  ".join("-" * w for w in widths))
    return "\n".join(lines)


def _slice_query(group_col: str, since: str | None) -> str:
    """Return a SQL string grouping discussions by ``group_col``.

    ``protocol_yield`` is pre-aggregated in a CTE so the LEFT JOIN is 1:1
    (same fix as ``v_token_efficiency`` — see ADR-0013).
    """
    where = "d.total_tokens_out IS NOT NULL"
    if since:
        where += f" AND d.created_at >= '{since}'"
    return f"""
        WITH py_agg AS (
            SELECT discussion_id,
                   SUM(findings_blocking) AS findings_blocking,
                   SUM(findings_advisory) AS findings_advisory
            FROM protocol_yield
            GROUP BY discussion_id
        )
        SELECT
            COALESCE(d.{group_col}, '(none)') AS bucket,
            COUNT(DISTINCT d.discussion_id) AS runs,
            ROUND(AVG(d.total_tokens_in), 0) AS avg_in,
            ROUND(AVG(d.total_tokens_out), 0) AS avg_out,
            ROUND(AVG(d.total_cache_tokens), 0) AS avg_cache,
            COALESCE(SUM(py.findings_blocking), 0) AS blocking,
            ROUND(
                CAST(COALESCE(SUM(py.findings_blocking), 0) AS REAL) * 1000.0 /
                NULLIF(SUM(d.total_tokens_out), 0),
                3
            ) AS blocking_per_1k_out
        FROM discussions d
        LEFT JOIN py_agg py ON py.discussion_id = d.discussion_id
        WHERE {where}
        GROUP BY bucket
        ORDER BY blocking_per_1k_out DESC NULLS LAST
    """


def _top_discussions_query(top: int, since: str | None) -> str:
    """Return a SQL string for the N most token-expensive discussions."""
    where = "d.total_tokens_out IS NOT NULL"
    if since:
        where += f" AND d.created_at >= '{since}'"
    return f"""
        WITH py_agg AS (
            SELECT discussion_id,
                   SUM(findings_blocking) AS findings_blocking
            FROM protocol_yield
            GROUP BY discussion_id
        )
        SELECT
            substr(d.discussion_id, 1, 36) AS discussion_id,
            d.command_type AS cmd,
            d.collaboration_mode AS mode,
            d.risk_level AS risk,
            d.total_tokens_out AS out_tokens,
            d.total_cache_tokens AS cache,
            COALESCE(py.findings_blocking, 0) AS blocking
        FROM discussions d
        LEFT JOIN py_agg py ON py.discussion_id = d.discussion_id
        WHERE {where}
        ORDER BY d.total_tokens_out DESC
        LIMIT {int(top)}
    """


def render_report(since: str | None = None, top: int = 10) -> str:
    """Build the full report as a single text string."""
    if not DB_PATH.exists():
        return f"Database not found at {DB_PATH}. Run scripts/init_db.py first."

    conn = sqlite3.connect(str(DB_PATH))
    try:
        sections: list[str] = []
        headers = [
            "bucket",
            "runs",
            "avg_in",
            "avg_out",
            "avg_cache",
            "blocking",
            "blocking_per_1k_out",
        ]
        for title, col in (
            ("By command_type", "command_type"),
            ("By collaboration_mode", "collaboration_mode"),
            ("By risk_level", "risk_level"),
        ):
            rows = conn.execute(_slice_query(col, since)).fetchall()
            sections.append(f"## {title}\n{_format_table(rows, headers)}")

        top_rows = conn.execute(_top_discussions_query(top, since)).fetchall()
        top_headers = ["discussion_id", "cmd", "mode", "risk", "out_tokens", "cache", "blocking"]
        sections.append(
            f"## Top {top} most expensive discussions (by output tokens)\n"
            f"{_format_table(top_rows, top_headers)}"
        )
    finally:
        conn.close()

    header = "# Efficiency Report"
    if since:
        header += f" (since {since})"
    note = (
        "\nNote: cost in dollars is NOT computed — token aggregates mix tiers.\n"
        "See config/model_pricing.yaml for rates if estimating a single-tier discussion.\n"
    )
    return f"{header}\n{note}\n" + "\n\n".join(sections) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Print a token-efficiency report.")
    parser.add_argument(
        "--since", default=None, help="Only include discussions created on/after YYYY-MM-DD."
    )
    parser.add_argument(
        "--top", type=int, default=10, help="How many most-expensive discussions to list."
    )
    args = parser.parse_args()
    print(render_report(since=args.since, top=args.top))


if __name__ == "__main__":
    main()
