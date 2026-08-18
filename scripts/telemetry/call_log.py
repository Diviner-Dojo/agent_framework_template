"""Durable per-call token/cache log (telemetry sensor, SPEC-20260716-093231).

Appends one JSON line per model call (assistant message) to
``metrics/model_call_log.jsonl`` with the three input-side usage numbers,
``output_tokens``, and the ``cache_read / total_input`` ratio — the leading
cache-health indicator the 2026-07-14 performance review found the framework
blind to. Transcripts under ``~/.claude`` are pruned over time; this log is
the durable per-call record that survives them.

Design notes (load-bearing):

* **Reuses the guarded parser.** Discovery/parse goes through
  ``scripts/ingest_token_usage`` (A-ARCH1 public helpers) — never re-walks
  ``~/.claude/projects`` itself, preserving the one-file-patch isolation and
  the symlink-traversal guard (regression ledger 2026-06-06).
* **Dedup state lives in the DB, not the file.** A
  ``{watermark_ts, boundary ids}`` record in ``telemetry_run_state``
  (``call_log_watermark``) makes each run incremental without ever re-reading
  the growing JSONL (the O(file) rescan ADR-0020 Alt-4 was rejected over).
  Consequently **deleting the JSONL does NOT rebuild it** — the watermark
  still considers old messages logged.
* **Flush-lag tolerance.** The watermark trails the newest logged message by
  ``FLUSH_LAG_SECONDS`` so a transcript line flushed to disk late (its
  timestamp older than wall-clock now) is still caught on the next run;
  boundary ids inside that window prevent duplicates.
* **Accepted concurrency/robustness bounds** (single-developer machine, no
  cross-process lock by design): two racing processes that both read the
  state before either writes can append valid duplicate lines, not just torn
  ones; a corrupt state blob degrades to a full rescan that re-logs history
  once; and chronic partial passes before the first-ever complete pass keep
  ``seen_ids`` unpruned until a complete pass sets the watermark. All three
  resolve to at-most-duplicate lines (readers dedup by ``message_id``) —
  never silent loss. A fourth bound IS a silent-loss case: a transcript file
  that first materializes on disk more than ``FLUSH_LAG_SECONDS`` after the
  watermark has advanced past its message timestamps (e.g. a long-running
  subagent flushing very late) is permanently skipped — the lag window is
  the accepted tolerance, not a guarantee (per-call telemetry is a sensor,
  not an audit log; the DB aggregates re-derive from full transcripts).
* **The ratio field is a recomputable grep convenience** derived from the
  same line's counts — not a stored metric in the ADR-0013 sense. Dollars are
  never logged (they would go stale on repricing; compute at read time).
* **Fields are opaque transcript-derived strings.** Future consumers must
  parse lines with ``json.loads`` only — never string-interpolate a field
  into a shell command, file path, or ``eval`` sink.
* **Growth**: append-only, gitignored. Rotation is deliberately deferred
  (YAGNI) — revisit when the file exceeds ~50 MB.

Usage:
    python scripts/telemetry/call_log.py                    # incremental pass
    python scripts/telemetry/call_log.py --budget-seconds 12
    python scripts/telemetry/call_log.py --from-hook        # summary on stderr,
                                                            # stdout stays silent
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import ingest_token_usage as itu  # noqa: E402
from scripts.init_db import init_db  # noqa: E402
from src.telemetry.cost import compute_cache_read_ratio  # noqa: E402

# Module-level and monkeypatchable (SPEC R7 write-side test isolation): every
# test overrides these to tmp_path targets, mirroring stop_hook.STATE_FILE.
DB_PATH = _REPO_ROOT / "metrics" / "evaluation.db"
LOG_PATH = _REPO_ROOT / "metrics" / "model_call_log.jsonl"
WATERMARK_KEY = "call_log_watermark"
# How far the watermark trails the newest logged message. A transcript line
# whose timestamp is older than this by the time it reaches disk is missed —
# accepted tolerance for concurrent-session flush lag.
FLUSH_LAG_SECONDS = 600


def _empty_summary() -> dict[str, object]:
    """Return the zeroed summary used on every early/no-op exit."""
    return {
        "calls_logged": 0,
        "partial": False,
        "watermark": None,
        "batch_cache_read_ratio": None,
    }


def _read_state(conn: sqlite3.Connection) -> tuple[datetime | None, dict[str, datetime]]:
    """Load ``(watermark_ts, boundary_ids)`` from ``telemetry_run_state``.

    Any missing/corrupt state degrades to a full scan ``(None, {})`` — the
    boundary-id map makes a rescan append no duplicates only for ids it still
    holds, so corruption is repaired by accepting a one-time full re-log risk
    on an empty map rather than crashing (fail-silent contract).
    """
    try:
        row = conn.execute(
            "SELECT value FROM telemetry_run_state WHERE key = ?", (WATERMARK_KEY,)
        ).fetchone()
    except sqlite3.OperationalError:
        return None, {}
    if not row or not row[0]:
        return None, {}
    try:
        raw = json.loads(row[0])
        wm = itu.parse_timestamp(raw.get("ts") or "")
        ids_raw = raw.get("ids")
        ids: dict[str, datetime] = {}
        if isinstance(ids_raw, dict):
            for message_id, ts_value in ids_raw.items():
                ts = itu.parse_timestamp(str(ts_value))
                if isinstance(message_id, str) and ts is not None:
                    ids[message_id] = ts
        return wm, ids
    except (json.JSONDecodeError, AttributeError, TypeError):
        return None, {}


def _write_state(
    conn: sqlite3.Connection, watermark: datetime | None, ids: dict[str, datetime]
) -> None:
    """Upsert the ``{ts, ids}`` state blob (atomic — a single SQLite upsert)."""
    payload = json.dumps(
        {
            "ts": watermark.isoformat() if watermark else None,
            "ids": {message_id: ts.isoformat() for message_id, ts in ids.items()},
        },
        ensure_ascii=True,
    )
    conn.execute(
        """INSERT INTO telemetry_run_state (key, value, updated_at)
           VALUES (?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                                          updated_at = excluded.updated_at""",
        (WATERMARK_KEY, payload, datetime.now(UTC).isoformat()),
    )


def _session_id_for(session_path: Path) -> str:
    """Derive the session id from a discovery unit (file stem or dir name)."""
    return session_path.stem if session_path.is_file() else session_path.name


def _record_line(record: itu.MessageRecord, session_id: str) -> str:
    """Serialize one MessageRecord to its JSONL line (ASCII-only)."""
    ratio = compute_cache_read_ratio(
        record.input_tokens, record.cache_read_tokens, record.cache_create_tokens
    )
    return json.dumps(
        {
            "ts": record.timestamp.isoformat(),
            "session_id": session_id,
            "source_kind": record.source_kind,
            "model": record.model,
            "input_tokens": record.input_tokens,
            "cache_read_input_tokens": record.cache_read_tokens,
            "cache_creation_input_tokens": record.cache_create_tokens,
            "output_tokens": record.output_tokens,
            "cache_read_ratio": round(ratio, 4) if ratio is not None else None,
            "message_id": record.message_id,
        },
        ensure_ascii=True,
    )


def _append_lines(log_path: Path, lines: list[str]) -> None:
    """Append lines with per-line flush, healing a truncated trailing line.

    A writer killed mid-append can leave the file without a trailing newline
    (AC12); starting this batch with a newline in that case keeps every new
    line independently parseable. Per-line flush bounds interleaving damage
    from a concurrent writer to single lines (accepted risk per spec).
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    needs_leading_newline = False
    try:
        with open(log_path, "rb") as handle:
            handle.seek(-1, 2)
            needs_leading_newline = handle.read(1) != b"\n"
    except OSError:
        needs_leading_newline = False  # missing or empty file
    with open(log_path, "a", encoding="utf-8") as handle:
        if needs_leading_newline:
            handle.write("\n")
            handle.flush()
        for line in lines:
            handle.write(line + "\n")
            handle.flush()


def run_call_log(
    *,
    db_path: Path | None = None,
    log_path: Path | None = None,
    project_root: Path | None = None,
    budget_seconds: float | None = None,
) -> dict[str, object]:
    """Run one incremental per-call logging pass.

    Args:
        db_path: SQLite database (defaults to the module constant; injectable).
        log_path: JSONL output (defaults to the module constant; injectable).
        project_root: Project whose transcripts to scan.
        budget_seconds: Optional cooperative deadline — checked between
            transcript files; on expiry the pass stops early and the watermark
            is NOT advanced (partial pass; the next run resumes).

    Returns:
        Summary dict: ``calls_logged``, ``partial``, ``watermark`` (ISO or
        ``None``), ``batch_cache_read_ratio`` (float or ``None``).
    """
    db_path = db_path or DB_PATH
    log_path = log_path or LOG_PATH
    project_root = project_root or itu.PROJECT_ROOT
    deadline = time.time() + budget_seconds if budget_seconds else None

    if not itu.CLAUDE_PROJECTS_ROOT.exists():
        return _empty_summary()
    session_paths = itu.discover_session_dirs(project_root)
    if not session_paths:
        return _empty_summary()
    if not db_path.exists():
        # No DB means no dedup state — logging without it would duplicate on
        # every run. Mirror analyze_cost's fail-clean precedent.
        return _empty_summary()
    init_db(db_path, quiet=True)  # ensure telemetry_run_state exists (idempotent)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        watermark, seen_ids = _read_state(conn)

        new_records: dict[str, tuple[itu.MessageRecord, str]] = {}
        partial = False
        for session_path in session_paths:
            if deadline is not None and time.time() >= deadline:
                partial = True
                break
            session_id = _session_id_for(session_path)
            for record in itu.parse_session_dir(session_path, deadline=deadline):
                # Eligibility: at-or-after the watermark (a strict '>' would
                # silently skip an unseen message sharing the watermark ts),
                # minus ids already logged inside the boundary window.
                if watermark is not None and record.timestamp < watermark:
                    continue
                if record.message_id in seen_ids or record.message_id in new_records:
                    continue
                new_records[record.message_id] = (record, session_id)
        if deadline is not None and time.time() >= deadline:
            partial = True

        ordered = sorted(new_records.values(), key=lambda pair: pair[0].timestamp)
        if ordered:
            _append_lines(log_path, [_record_line(rec, sid) for rec, sid in ordered])

        # State update. Partial pass: watermark unchanged so unscanned files
        # are retried; merged ids prevent re-logging what we did write.
        merged = dict(seen_ids)
        merged.update({rec.message_id: rec.timestamp for rec, _ in new_records.values()})
        if partial or not ordered:
            new_watermark = watermark
        else:
            newest = max(rec.timestamp for rec, _ in ordered)
            lagged = newest - timedelta(seconds=FLUSH_LAG_SECONDS)
            new_watermark = max(watermark, lagged) if watermark else lagged
        if new_watermark is not None:
            merged = {mid: ts for mid, ts in merged.items() if ts >= new_watermark}
        _write_state(conn, new_watermark, merged)
        conn.commit()
    finally:
        conn.close()

    sum_in = sum(r.input_tokens or 0 for r, _ in ordered)
    sum_cr = sum(r.cache_read_tokens or 0 for r, _ in ordered)
    sum_cc = sum(r.cache_create_tokens or 0 for r, _ in ordered)
    batch_ratio = compute_cache_read_ratio(sum_in, sum_cr, sum_cc) if ordered else None
    return {
        "calls_logged": len(ordered),
        "partial": partial,
        "watermark": new_watermark.isoformat() if new_watermark else None,
        "batch_cache_read_ratio": round(batch_ratio, 4) if batch_ratio is not None else None,
    }


def main() -> None:
    """CLI entry point. ``--from-hook`` keeps stdout silent (stderr summary).

    The stop-hook invokes this script as a subprocess with captured output;
    the ``--from-hook`` stderr routing is defense in depth so the hook's
    stdout (reserved for its single JSON decision object) can never be
    polluted even if the capture is removed (SPEC AC11).
    """
    parser = argparse.ArgumentParser(
        description="Append per-call token/cache usage to metrics/model_call_log.jsonl."
    )
    parser.add_argument(
        "--from-hook",
        action="store_true",
        help="Invoked by stop_hook.py: write the summary to stderr, not stdout.",
    )
    parser.add_argument(
        "--budget-seconds",
        type=float,
        default=None,
        help="Cooperative deadline; the pass stops early (partial) on expiry.",
    )
    args = parser.parse_args()

    summary = run_call_log(budget_seconds=args.budget_seconds)

    stream = sys.stderr if args.from_hook else sys.stdout
    ratio = summary["batch_cache_read_ratio"]
    ratio_text = f"{ratio:.4f}" if isinstance(ratio, float) else "n/a"
    partial_text = " (partial pass)" if summary["partial"] else ""
    print(
        f"call-log: {summary['calls_logged']} call(s) logged{partial_text}, "
        f"batch cache-read ratio {ratio_text}, watermark {summary['watermark'] or 'none'}",
        file=stream,
    )


if __name__ == "__main__":
    main()
