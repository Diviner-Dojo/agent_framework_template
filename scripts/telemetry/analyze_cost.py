"""Build the per-discussion, per-model token breakdown (telemetry Layer A1).

This is the I/O / transport layer for per-tier dollar cost. It **reuses** the
ADR-0013 transcript parser in ``scripts/ingest_token_usage.py`` rather than
re-walking ``~/.claude/projects`` itself, preserving that path's one-file-patch
isolation and its symlink-traversal guard. The pure cost math lives in
``src/telemetry/{pricing,cost}.py``.

It persists the per-model token breakdown (the **cost input**) to
``discussion_model_tokens`` — never a dollar figure (ADR-0013 compute-don't-
store). Cost is computed at read time from ``config/model_pricing.yaml``.

Incremental by default via a watermark in ``telemetry_run_state``
(``cost_last_analyzed_at``); ``--full-rescan`` reprocesses everything. Writes
are idempotent: a discussion's rows are deleted and rewritten each run, so two
identical runs leave identical state.

Transport-fidelity boundary: transcript discovery/parse is exercised only
through integration tests with monkeypatched roots and tmp fixtures; live
``~/.claude`` discovery is not under unit test (spec R-A5).

Usage:
    python scripts/telemetry/analyze_cost.py                 # incremental
    python scripts/telemetry/analyze_cost.py --full-rescan   # reprocess all
    python scripts/telemetry/analyze_cost.py --dry-run
    python scripts/telemetry/analyze_cost.py --since YYYY-MM-DD
    python scripts/telemetry/analyze_cost.py --discussion DISC-...
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import ingest_token_usage as itu  # noqa: E402
from scripts.init_db import init_db  # noqa: E402
from src.telemetry.cost import CostReport, ModelTokenRow, build_cost_report  # noqa: E402
from src.telemetry.pricing import UNKNOWN_TIER, PricingTable, load_pricing  # noqa: E402

DB_PATH = _REPO_ROOT / "metrics" / "evaluation.db"
WATERMARK_KEY = "cost_last_analyzed_at"


def _empty_summary() -> dict[str, int]:
    """Return the zeroed summary returned on every early/no-op exit."""
    return {
        "sessions": 0,
        "messages_seen": 0,
        "messages_attributed": 0,
        "discussions_written": 0,
        "models_written": 0,
    }


def _read_watermark(conn: sqlite3.Connection) -> str | None:
    """Return the stored cost watermark (ISO timestamp), or ``None``."""
    try:
        row = conn.execute(
            "SELECT value FROM telemetry_run_state WHERE key = ?", (WATERMARK_KEY,)
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    return row[0] if row and row[0] else None


def _write_watermark(conn: sqlite3.Connection, value: str) -> None:
    """Upsert the cost watermark."""
    conn.execute(
        """INSERT INTO telemetry_run_state (key, value, updated_at)
           VALUES (?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                                          updated_at = excluded.updated_at""",
        (WATERMARK_KEY, value, datetime.now(UTC).isoformat()),
    )


def _analyzed_discussion_ids(conn: sqlite3.Connection) -> set[str]:
    """Return discussion ids that already have a breakdown row (= analyzed)."""
    return {
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT discussion_id FROM discussion_model_tokens"
        ).fetchall()
    }


def _target_discussion_ids(
    conn: sqlite3.Connection,
    *,
    watermark: str | None,
    full_rescan: bool,
    discussion_filter: str | None,
    analyzed: set[str],
) -> set[str]:
    """Return the discussion ids to (re)compute this run.

    Full rescan (or no watermark) selects everything. Otherwise: still-open
    discussions are always recomputed (they keep accumulating); a closed
    discussion that has **never been analyzed** (no breakdown rows) is always a
    target; and an already-analyzed closed discussion is recomputed only when its
    ``closed_at`` is newer than the watermark.

    The not-yet-analyzed backstop is a correctness guard: two discussions can
    share an exact ``closed_at``, so a strict ``closed_at > watermark`` test
    alone would silently skip a *new* discussion whose ``closed_at`` equals the
    watermark set by a prior run. (A closed discussion that genuinely produces no
    cost rows is harmlessly re-attempted each run — it writes nothing.)
    """
    if discussion_filter:
        return {discussion_filter}
    rows = conn.execute("SELECT discussion_id, status, closed_at FROM discussions").fetchall()
    wm = itu.parse_timestamp(watermark) if watermark else None
    targets: set[str] = set()
    for discussion_id, status, closed_at in rows:
        if full_rescan or wm is None:
            targets.add(discussion_id)
            continue
        if status != "closed" or not closed_at:
            targets.add(discussion_id)
            continue
        if discussion_id not in analyzed:  # never analyzed -> always a target
            targets.add(discussion_id)
            continue
        closed_dt = itu.parse_timestamp(closed_at)
        if closed_dt is None or closed_dt > wm:
            targets.add(discussion_id)
    return targets


def _max_closed_at(conn: sqlite3.Connection) -> str | None:
    """Return the newest ``closed_at`` among closed discussions, or ``None``."""
    row = conn.execute(
        "SELECT MAX(closed_at) FROM discussions WHERE status = 'closed' AND closed_at IS NOT NULL"
    ).fetchone()
    return row[0] if row and row[0] else None


def _bucket_messages(
    messages: dict[str, itu.MessageRecord],
    windows: list[itu.DiscussionWindow],
    targets: set[str],
) -> tuple[dict[tuple[str, str], dict[str, int]], int]:
    """Group dedup'd messages into (discussion_id, model_id) token buckets.

    Only messages attributed to a *target* discussion are bucketed. A message
    with no model id is bucketed under the ``unknown`` sentinel.

    Returns:
        ``(buckets, attributed_count)`` where each bucket holds summed
        ``in``/``out``/``cr``/``cc`` tokens and a message count ``n``.
    """
    buckets: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {"in": 0, "out": 0, "cr": 0, "cc": 0, "n": 0}
    )
    attributed = 0
    for message in messages.values():
        discussion_id = itu._attribute(message, windows)
        if discussion_id is None or discussion_id not in targets:
            continue
        attributed += 1
        model_id = message.model or UNKNOWN_TIER
        bucket = buckets[(discussion_id, model_id)]
        bucket["in"] += message.input_tokens or 0
        bucket["out"] += message.output_tokens or 0
        bucket["cr"] += message.cache_read_tokens or 0
        bucket["cc"] += message.cache_create_tokens or 0
        bucket["n"] += 1
    return buckets, attributed


def _write_breakdown(
    conn: sqlite3.Connection,
    buckets: dict[tuple[str, str], dict[str, int]],
    targets: set[str],
    pricing: PricingTable,
) -> int:
    """Replace breakdown rows for every target discussion (idempotent).

    Deleting all rows for a target before inserting guarantees a stale model row
    (e.g. a discussion re-attributed differently) cannot linger.

    Returns:
        The number of (discussion, model) rows written.
    """
    now = datetime.now(UTC).isoformat()
    for discussion_id in targets:
        conn.execute(
            "DELETE FROM discussion_model_tokens WHERE discussion_id = ?", (discussion_id,)
        )
    written = 0
    for (discussion_id, model_id), bucket in buckets.items():
        resolve_id = None if model_id == UNKNOWN_TIER else model_id
        tier = pricing.resolve_tier(resolve_id)
        # Plain INSERT: the per-target DELETE above is the idempotency strategy,
        # so the row cannot already exist. INSERT (not OR REPLACE) fails loudly
        # if that DELETE is ever removed or mis-scoped.
        conn.execute(
            """INSERT INTO discussion_model_tokens
               (discussion_id, model_id, tier, tokens_in, tokens_out,
                cache_read_tokens, cache_create_tokens, message_count, computed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                discussion_id,
                model_id,
                tier,
                bucket["in"],
                bucket["out"],
                bucket["cr"],
                bucket["cc"],
                bucket["n"],
                now,
            ),
        )
        written += 1
    return written


def load_cost_rows(
    conn: sqlite3.Connection, discussion_filter: str | None = None
) -> list[ModelTokenRow]:
    """Load stored breakdown rows as :class:`ModelTokenRow` values."""
    sql = (
        "SELECT discussion_id, model_id, tier, tokens_in, tokens_out, "
        "cache_read_tokens, cache_create_tokens, message_count "
        "FROM discussion_model_tokens"
    )
    params: tuple[str, ...] = ()
    if discussion_filter:
        sql += " WHERE discussion_id = ?"
        params = (discussion_filter,)
    return [ModelTokenRow(*row) for row in conn.execute(sql, params).fetchall()]


def analyze_cost(
    *,
    db_path: Path = DB_PATH,
    project_root: Path | None = None,
    since: datetime | None = None,
    discussion_filter: str | None = None,
    full_rescan: bool = False,
    dry_run: bool = False,
    pricing: PricingTable | None = None,
) -> dict[str, int]:
    """Build the per-model breakdown and return a run summary.

    Args:
        db_path: SQLite database path (injectable for tests).
        project_root: Project whose transcripts to scan (defaults to the
            framework root used by ``ingest_token_usage``).
        since: Ignore messages older than this timestamp.
        discussion_filter: Restrict to a single discussion id.
        full_rescan: Ignore the watermark and reprocess every discussion.
        dry_run: Compute and report but do not write.
        pricing: Pricing table (defaults to loading the YAML).

    Returns:
        A summary dict (sessions, messages seen/attributed, rows written).
    """
    project_root = project_root or itu.PROJECT_ROOT
    if not itu.CLAUDE_PROJECTS_ROOT.exists():
        print(f"Claude Code transcript root not found: {itu.CLAUDE_PROJECTS_ROOT}. Nothing to do.")
        return _empty_summary()
    session_paths = itu.discover_session_dirs(project_root)
    if not session_paths:
        print(f"No session transcripts for project under {itu.CLAUDE_PROJECTS_ROOT}.")
        return _empty_summary()
    if not db_path.exists():
        print(f"SQLite database not found at {db_path}. Run scripts/init_db.py first.")
        return _empty_summary()

    pricing = pricing or load_pricing()
    init_db(db_path, quiet=True)  # ensure telemetry tables exist (shared, idempotent schema)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        messages = itu.collect_messages(session_paths, since)
        windows = itu.load_discussion_windows(conn, discussion_filter)
        watermark = None if full_rescan else _read_watermark(conn)
        analyzed = _analyzed_discussion_ids(conn)
        targets = _target_discussion_ids(
            conn,
            watermark=watermark,
            full_rescan=full_rescan,
            discussion_filter=discussion_filter,
            analyzed=analyzed,
        )
        buckets, attributed = _bucket_messages(messages, windows, targets)

        written = 0
        if not dry_run:
            written = _write_breakdown(conn, buckets, targets, pricing)
            new_watermark = _max_closed_at(conn)
            if new_watermark:
                _write_watermark(conn, new_watermark)
            conn.commit()

        report = build_cost_report(load_cost_rows(conn, discussion_filter), pricing)
        _print_report(report, dry_run=dry_run)
        return {
            "sessions": len(session_paths),
            "messages_seen": len(messages),
            "messages_attributed": attributed,
            "discussions_written": len({did for did, _ in buckets}),
            "models_written": written,
        }
    finally:
        conn.close()


def _print_report(report: CostReport, *, dry_run: bool) -> None:
    """Print a per-tier cost summary with an explicit coverage figure."""
    prefix = "[dry-run] " if dry_run else ""
    print(f"{prefix}Per-tier cost (USD), coverage {report.coverage_pct}% of billable tokens:")
    for tier in sorted(report.by_tier):
        tc = report.by_tier[tier]
        if tc.cost_usd is None:
            cost = "uncosted (unknown tier)"
        else:
            cost = f"${tc.cost_usd:,.4f}"
        print(f"  {tier:8} {tc.total_tokens():>12,} tok  {cost}")
    print(
        f"{prefix}TOTAL known cost: ${report.total_cost_usd:,.4f} "
        f"({report.known_tokens:,}/{report.total_tokens:,} tokens priced)"
    )
    if not report.is_fully_covered and report.total_tokens > 0:
        print(
            f"{prefix}NOTE: {100.0 - report.coverage_pct:.1f}% of tokens are an unknown tier "
            "and are excluded from the cost total (not zero-rated)."
        )


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Build per-model token breakdown + per-tier cost (telemetry Layer A1)."
    )
    parser.add_argument("--full-rescan", action="store_true", help="Ignore the watermark.")
    parser.add_argument("--dry-run", action="store_true", help="Report only; do not write.")
    parser.add_argument("--since", default=None, help="Ignore messages before YYYY-MM-DD (UTC).")
    parser.add_argument("--discussion", default=None, help="Restrict to one discussion id.")
    args = parser.parse_args()

    summary = analyze_cost(
        since=itu.parse_since(args.since),
        discussion_filter=args.discussion,
        full_rescan=args.full_rescan,
        dry_run=args.dry_run,
    )
    prefix = "[dry-run] " if args.dry_run else ""
    print(
        f"{prefix}Scanned {summary['sessions']} session path(s); saw "
        f"{summary['messages_seen']} message(s); attributed {summary['messages_attributed']}; "
        f"wrote {summary['models_written']} model row(s) across "
        f"{summary['discussions_written']} discussion(s)."
    )


if __name__ == "__main__":
    main()
