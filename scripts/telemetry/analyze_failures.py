"""Detect agent failure / token-waste signals from session transcripts (A2).

This is the I/O / transport layer for Telemetry Layer A2 (ADR-0020). It walks the
real ``~/.claude/projects`` transcripts, parses the tool-use / tool-result /
subagent-lifecycle events that the ADR-0013 token parser discards, and feeds them
to the pure detectors in ``src/telemetry/failures.py``. It persists detected
failures (the WASTED token counts + tier — the cost input) to
``telemetry_failures``; the dollar weight used for ranking is computed at read
time from ``config/model_pricing.yaml`` (compute-don't-store, ADR-0013).

Grounded on real transcripts (see the ``reference_subagent_transcript_layout``
memory), NOT on the spec's assumptions:

* The dispatch tool is named ``Agent`` (not ``Task``); its input carries
  ``subagent_type`` and an optional ``run_in_background``.
* Subagent transcripts live in ``<sessionId>/subagents/agent-<id>.jsonl`` and
  carry no back-link to their dispatch ``tool_use_id`` — so a no-result orphan is
  detected parent-side (tokens left honestly uncosted) and a hung subagent is
  detected from its own transcript's non-clean terminal + its own token usage.

Incremental via an **mtime watermark** (``failures_last_analyzed_mtime`` in
``telemetry_run_state``): a re-run only re-parses session files whose mtime is
``>= `` the watermark. Using ``>=`` (not ``>``) re-processes the boundary file
set, which closes the same-timestamp silent-skip hole the A1 review found —
cheaply, because the unit is a file with a high-resolution mtime and writes are
idempotent (DELETE-then-INSERT per session). ``--full-rescan`` ignores it.

Transport-fidelity boundary: transcript discovery/parse is exercised through
integration tests with monkeypatched roots and tmp fixtures; live ``~/.claude``
discovery is not under unit test (spec R-A5).

Usage:
    python scripts/telemetry/analyze_failures.py                 # incremental
    python scripts/telemetry/analyze_failures.py --full-rescan   # reprocess all
    python scripts/telemetry/analyze_failures.py --dry-run
    python scripts/telemetry/analyze_failures.py --top 20
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import ingest_token_usage as itu  # noqa: E402
from scripts.init_db import init_db  # noqa: E402
from src.telemetry.failures import (  # noqa: E402
    FailureSignal,
    RankedFailure,
    SubagentDispatch,
    SubagentRun,
    ToolCall,
    detect_orphaned_subagents,
    detect_retry_loops,
    rank_failures,
)
from src.telemetry.pricing import PricingTable, load_pricing  # noqa: E402

DB_PATH = _REPO_ROOT / "metrics" / "evaluation.db"
WATERMARK_KEY = "failures_last_analyzed_mtime"

#: Stop reasons that mean "the subagent's last turn was waiting on a tool" — i.e.
#: the transcript ends mid-flight rather than on a returned answer.
_INCOMPLETE_STOP_REASONS = frozenset({"tool_use"})


def _empty_summary() -> dict[str, int]:
    """Return the zeroed summary returned on every early/no-op exit."""
    return {
        "sessions_seen": 0,
        "sessions_analyzed": 0,
        "retry_loops": 0,
        "orphaned_subagents": 0,
        "rows_written": 0,
    }


def _input_hash(tool_input: object) -> str:
    """Return a short stable hash of a tool input (canonical JSON, sorted keys)."""
    try:
        canonical = json.dumps(tool_input, sort_keys=True, default=str, ensure_ascii=True)
    except (TypeError, ValueError):
        canonical = repr(tool_input)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _iter_records(path: Path) -> Iterator[dict]:
    """Yield parsed JSON object records from a JSONL file, skipping bad lines."""
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    yield obj
    except OSError:
        return


def _usage_tokens(message: dict) -> tuple[int | None, int | None, int | None, int | None]:
    """Extract (in, out, cache_read, cache_create) from a message's usage block."""
    usage = message.get("usage")
    if not isinstance(usage, dict):
        return (None, None, None, None)
    return (
        itu.coerce_int(usage.get("input_tokens")),
        itu.coerce_int(usage.get("output_tokens")),
        itu.coerce_int(usage.get("cache_read_input_tokens")),
        itu.coerce_int(usage.get("cache_creation_input_tokens")),
    )


def parse_main_session(
    path: Path, pricing: PricingTable
) -> tuple[list[ToolCall], list[SubagentDispatch], set[str]]:
    """Parse a parent session transcript into call stream, dispatches, results.

    Args:
        path: The ``<sessionId>.jsonl`` parent transcript.
        pricing: Pricing table used to resolve each call's tier.

    Returns:
        ``(tool_calls, dispatches, result_ids)`` — tool_calls in chronological
        order (for retry-loop detection); ``Agent`` dispatches; and the set of
        ``tool_use_id``s that received a ``tool_result``.
    """
    tool_calls: list[ToolCall] = []
    dispatches: list[SubagentDispatch] = []
    result_ids: set[str] = set()
    for record in _iter_records(path):
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        ts = itu.parse_timestamp(record.get("timestamp", ""))
        role = message.get("role")
        if role == "assistant":
            model = message.get("model") if isinstance(message.get("model"), str) else None
            tier = pricing.resolve_tier(model)
            t_in, t_out, c_read, c_create = _usage_tokens(message)
            message_id = message.get("id") or record.get("uuid") or ""
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                name = block.get("name") or ""
                tool_input = block.get("input")
                tool_calls.append(
                    ToolCall(
                        name=name,
                        input_hash=_input_hash(tool_input),
                        message_id=message_id,
                        tier=tier,
                        tokens_in=t_in,
                        tokens_out=t_out,
                        cache_read_tokens=c_read,
                        cache_create_tokens=c_create,
                        timestamp=ts,
                    )
                )
                if name == "Agent" and isinstance(tool_input, dict):
                    dispatches.append(
                        SubagentDispatch(
                            tool_use_id=block.get("id") or "",
                            subagent_type=str(tool_input.get("subagent_type") or "unknown"),
                            timestamp=ts,
                            run_in_background=bool(tool_input.get("run_in_background")),
                        )
                    )
        elif role == "user":
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    tid = block.get("tool_use_id")
                    if tid:
                        result_ids.add(tid)
    return tool_calls, dispatches, result_ids


def parse_subagent_run(path: Path, pricing: PricingTable) -> SubagentRun:
    """Summarise one ``agent-<id>.jsonl`` transcript into a :class:`SubagentRun`.

    ``completed`` is True iff the last message-bearing record is an assistant turn
    whose ``stop_reason`` is not ``tool_use`` (a returned answer rather than a
    transcript that ends waiting on a tool). Token usage is summed over assistant
    messages, de-duplicated by message id.
    """
    agent_id = path.stem[len("agent-") :] if path.stem.startswith("agent-") else path.stem
    seen_ids: set[str] = set()
    t_in = t_out = c_read = c_create = 0
    any_tokens = False
    models: dict[str, int] = {}
    last_role: str | None = None
    last_stop: str | None = None
    first_ts: datetime | None = None
    last_ts: datetime | None = None
    for record in _iter_records(path):
        ts = itu.parse_timestamp(record.get("timestamp", ""))
        if ts is not None:
            first_ts = ts if first_ts is None else min(first_ts, ts)
            last_ts = ts if last_ts is None else max(last_ts, ts)
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        agent_id = record.get("agentId") or agent_id
        role = message.get("role")
        if role:
            last_role = role
            last_stop = message.get("stop_reason")
        if role == "assistant":
            model = message.get("model") if isinstance(message.get("model"), str) else None
            if model:
                models[model] = models.get(model, 0) + 1
            message_id = message.get("id") or record.get("uuid") or ""
            if message_id in seen_ids:
                continue
            seen_ids.add(message_id)
            ai, ao, ar, ac = _usage_tokens(message)
            if any(v is not None for v in (ai, ao, ar, ac)):
                any_tokens = True
                t_in += ai or 0
                t_out += ao or 0
                c_read += ar or 0
                c_create += ac or 0
    dominant_model = max(models, key=lambda m: models[m]) if models else None
    # Validated on 399 real subagent transcripts: 397 healthy ones end on an
    # assistant turn (end_turn / stop_sequence / a bare None stop_reason are all
    # clean completions), and only 2 — the genuinely hung ones — end on a
    # non-assistant (user) record. So "last record is an assistant turn" is the
    # real discriminator; a final assistant turn with stop_reason 'tool_use'
    # (cut off waiting on a tool) is the one assistant terminal that still counts
    # as incomplete. An empty transcript (last_role None) is correctly incomplete.
    completed = last_role == "assistant" and last_stop not in _INCOMPLETE_STOP_REASONS
    return SubagentRun(
        agent_id=agent_id,
        source_tool_use_id=None,  # subagent files carry no dispatch back-link
        completed=completed,
        tier=pricing.resolve_tier(dominant_model),
        tokens_in=t_in if any_tokens else None,
        tokens_out=t_out if any_tokens else None,
        cache_read_tokens=c_read if any_tokens else None,
        cache_create_tokens=c_create if any_tokens else None,
        first_seen=first_ts,
        last_seen=last_ts,
    )


def _group_sessions(session_paths: list[Path]) -> dict[str, dict[str, object]]:
    """Group discovered paths by session id into {main_file, subagent_dir}.

    ``discover_session_dirs`` returns a mix of ``<sessionId>.jsonl`` files and
    ``<sessionId>`` directories; this pairs them by id so each session is one
    unit of work (main transcript + its ``subagents/`` siblings).
    """
    groups: dict[str, dict[str, object]] = {}
    for path in session_paths:
        if path.is_file() and path.suffix == ".jsonl":
            sid = path.stem
            groups.setdefault(sid, {})["main"] = path
        elif path.is_dir():
            sid = path.name
            sub = path / "subagents"
            if sub.is_dir():
                groups.setdefault(sid, {})["subagents"] = sub
            # A session dir may also hold its own <sessionId>.jsonl.
            inner = path / f"{sid}.jsonl"
            if inner.is_file():
                groups.setdefault(sid, {}).setdefault("main", inner)
    return groups


def _session_mtime(group: dict[str, object]) -> float:
    """Return the newest mtime across a session's main + subagent files.

    The subagents directory is walked with ``os.scandir`` so each entry's mtime
    comes from the directory read itself — ``DirEntry.stat()`` and ``is_file()``
    are syscall-free for normal files (a reparse point / symlink still issues a
    real ``stat()``), avoiding a separate ``stat()`` per file (review advisory,
    perf). Each entry is bounds-checked with ``itu._is_inside_projects_root``
    before it is stat'd, mirroring the symlink-escape guard ``_detect_for_session``
    applies before opening files (review advisory, security — stat parity).
    """
    mtimes: list[float] = []
    main = group.get("main")
    if isinstance(main, Path):
        try:
            mtimes.append(main.stat().st_mtime)
        except OSError:
            pass
    sub = group.get("subagents")
    if isinstance(sub, Path):
        try:
            with os.scandir(sub) as entries:
                for entry in entries:
                    if not (entry.name.endswith(".jsonl") and entry.is_file()):
                        continue
                    if not itu._is_inside_projects_root(Path(entry.path)):
                        continue
                    try:
                        mtimes.append(entry.stat().st_mtime)
                    except OSError:
                        pass
        except OSError:
            pass
    return max(mtimes) if mtimes else 0.0


def _read_watermark(conn: sqlite3.Connection) -> float | None:
    """Return the stored mtime watermark (epoch seconds), or ``None``."""
    try:
        row = conn.execute(
            "SELECT value FROM telemetry_run_state WHERE key = ?", (WATERMARK_KEY,)
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row or not row[0]:
        return None
    try:
        return float(row[0])
    except (TypeError, ValueError):
        return None


def _write_watermark(conn: sqlite3.Connection, value: float) -> None:
    """Upsert the mtime watermark."""
    conn.execute(
        """INSERT INTO telemetry_run_state (key, value, updated_at)
           VALUES (?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                                          updated_at = excluded.updated_at""",
        (WATERMARK_KEY, repr(value), datetime.now(UTC).isoformat()),
    )


def _attribute_ts(ts: datetime | None, windows: list[itu.DiscussionWindow]) -> str | None:
    """Return the discussion id whose window contains ``ts``, or ``None``."""
    if ts is None:
        return None
    for window in windows:
        if window.start <= ts <= window.end:
            return window.discussion_id
    return None


def _detect_for_session(
    group: dict[str, object], pricing: PricingTable, retry_threshold: int
) -> list[FailureSignal]:
    """Run both detectors over one grouped session and return its signals.

    Every file is re-checked with ``itu._is_inside_projects_root`` before it is
    opened — the same symlink-traversal guard ``itu._iter_jsonl_files`` applies —
    so a symlink planted under ``subagents/`` that escapes the projects root is
    skipped rather than read (defense in depth even though discovery also guards).
    """
    signals: list[FailureSignal] = []
    main = group.get("main")
    dispatches: list[SubagentDispatch] = []
    result_ids: set[str] = set()
    if isinstance(main, Path) and itu._is_inside_projects_root(main):
        tool_calls, dispatches, result_ids = parse_main_session(main, pricing)
        signals.extend(detect_retry_loops(tool_calls, threshold=retry_threshold))
    runs: list[SubagentRun] = []
    sub = group.get("subagents")
    if isinstance(sub, Path):
        for entry in sorted(sub.iterdir()):
            if (
                entry.is_file()
                and entry.suffix == ".jsonl"
                and entry.name.startswith("agent-")
                and itu._is_inside_projects_root(entry)
            ):
                runs.append(parse_subagent_run(entry, pricing))
    signals.extend(detect_orphaned_subagents(dispatches, result_ids, runs))
    return signals


def _write_session_failures(
    conn: sqlite3.Connection,
    session_id: str,
    signals: list[FailureSignal],
    windows: list[itu.DiscussionWindow],
) -> int:
    """Idempotently replace a session's failure rows. Returns rows written."""
    conn.execute("DELETE FROM telemetry_failures WHERE session_id = ?", (session_id,))
    now = datetime.now(UTC).isoformat()
    written = 0
    for sig in signals:
        discussion_id = _attribute_ts(sig.first_seen, windows)
        conn.execute(
            """INSERT INTO telemetry_failures
               (session_id, discussion_id, failure_type, signature, occurrence_count,
                tier, wasted_tokens_in, wasted_tokens_out, wasted_cache_read_tokens,
                wasted_cache_create_tokens, detail, first_seen, last_seen, computed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                discussion_id,
                sig.failure_type,
                sig.signature,
                sig.occurrence_count,
                sig.tier,
                sig.wasted_tokens_in,
                sig.wasted_tokens_out,
                sig.wasted_cache_read_tokens,
                sig.wasted_cache_create_tokens,
                sig.detail,
                sig.first_seen.isoformat() if sig.first_seen else None,
                sig.last_seen.isoformat() if sig.last_seen else None,
                now,
            ),
        )
        written += 1
    return written


def load_failure_signals(conn: sqlite3.Connection) -> list[FailureSignal]:
    """Load all stored failure rows back into :class:`FailureSignal` values."""
    rows = conn.execute(
        """SELECT failure_type, signature, occurrence_count, tier,
                  wasted_tokens_in, wasted_tokens_out, wasted_cache_read_tokens,
                  wasted_cache_create_tokens, detail, first_seen, last_seen
           FROM telemetry_failures"""
    ).fetchall()
    signals: list[FailureSignal] = []
    for r in rows:
        signals.append(
            FailureSignal(
                failure_type=r[0],
                signature=r[1],
                occurrence_count=r[2],
                tier=r[3],
                wasted_tokens_in=r[4],
                wasted_tokens_out=r[5],
                wasted_cache_read_tokens=r[6],
                wasted_cache_create_tokens=r[7],
                detail=r[8] or "",
                first_seen=itu.parse_timestamp(r[9]) if r[9] else None,
                last_seen=itu.parse_timestamp(r[10]) if r[10] else None,
            )
        )
    return signals


def analyze_failures(
    *,
    db_path: Path = DB_PATH,
    project_root: Path | None = None,
    full_rescan: bool = False,
    dry_run: bool = False,
    retry_threshold: int = 3,
    top: int = 15,
    pricing: PricingTable | None = None,
) -> dict[str, int]:
    """Detect failure signals across a project's sessions and persist them.

    Args:
        db_path: SQLite database path (injectable for tests).
        project_root: Project whose transcripts to scan (defaults to the
            framework root used by ``ingest_token_usage``).
        full_rescan: Ignore the mtime watermark and reprocess every session.
        dry_run: Compute and report but do not write.
        retry_threshold: Identical-consecutive-call count that flags a loop.
        top: Number of ranked failures to print.
        pricing: Pricing table (defaults to loading the YAML).

    Returns:
        A run summary dict.
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

    groups = _group_sessions(session_paths)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        windows = itu.load_discussion_windows(conn, None)
        watermark = None if full_rescan else _read_watermark(conn)

        targets: dict[str, tuple[dict[str, object], float]] = {}
        for sid, group in groups.items():
            mtime = _session_mtime(group)
            if full_rescan or watermark is None or mtime >= watermark:
                targets[sid] = (group, mtime)

        rows_written = 0
        retry_count = 0
        orphan_count = 0
        max_mtime = watermark or 0.0
        analyzed_signals: list[FailureSignal] = []  # detected this run (for dry-run report)
        for sid, (group, mtime) in targets.items():
            signals = _detect_for_session(group, pricing, retry_threshold)
            analyzed_signals.extend(signals)
            retry_count += sum(1 for s in signals if s.failure_type == "retry_loop")
            orphan_count += sum(1 for s in signals if s.failure_type == "orphaned_subagent")
            if not dry_run:
                rows_written += _write_session_failures(conn, sid, signals, windows)
            max_mtime = max(max_mtime, mtime)

        if not dry_run:
            if max_mtime > 0.0:
                _write_watermark(conn, max_mtime)
            conn.commit()

        # Non-dry-run reports the full stored corpus (incremental runs only
        # re-detect changed sessions, but the report should reflect everything).
        report_signals = load_failure_signals(conn) if not dry_run else analyzed_signals
        _print_report(rank_failures(report_signals, pricing), top=top, dry_run=dry_run)
        return {
            "sessions_seen": len(groups),
            "sessions_analyzed": len(targets),
            "retry_loops": retry_count,
            "orphaned_subagents": orphan_count,
            "rows_written": rows_written,
        }
    finally:
        conn.close()


def _print_report(ranked: list[RankedFailure], *, top: int, dry_run: bool) -> None:
    """Print the cost-weighted failure ranking with an honest uncosted marker."""
    prefix = "[dry-run] " if dry_run else ""
    total = len(ranked)
    print(f"{prefix}Detected {total} failure signal(s), cost-weighted (most wasteful first):")
    if not total:
        print("  (none — no retry loops or orphaned subagents detected)")
        return
    for rf in ranked[:top]:
        s = rf.signal
        cost = "uncosted (unknown tier)" if rf.cost_usd is None else f"${rf.cost_usd:,.4f}"
        print(
            f"  {s.failure_type:18} {cost:>26}  "
            f"{s.wasted_total_tokens():>10,} tok  {s.tier:7}  {s.detail}"
        )
    if total > top:
        print(f"  … and {total - top} more (raise --top to see them).")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Detect agent failure/waste signals from transcripts (telemetry Layer A2)."
    )
    parser.add_argument("--full-rescan", action="store_true", help="Ignore the mtime watermark.")
    parser.add_argument("--dry-run", action="store_true", help="Report only; do not write.")
    parser.add_argument(
        "--retry-threshold", type=int, default=3, help="Identical-consecutive calls = a loop."
    )
    parser.add_argument("--top", type=int, default=15, help="How many ranked failures to print.")
    args = parser.parse_args()

    summary = analyze_failures(
        full_rescan=args.full_rescan,
        dry_run=args.dry_run,
        retry_threshold=args.retry_threshold,
        top=args.top,
    )
    prefix = "[dry-run] " if args.dry_run else ""
    print(
        f"{prefix}Scanned {summary['sessions_seen']} session(s); analyzed "
        f"{summary['sessions_analyzed']}; found {summary['retry_loops']} retry loop(s) + "
        f"{summary['orphaned_subagents']} orphaned subagent(s); wrote "
        f"{summary['rows_written']} row(s)."
    )


if __name__ == "__main__":
    main()
