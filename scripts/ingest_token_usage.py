"""Ingest Claude Code token usage from session transcripts into SQLite.

Implements the post-hoc-ingest model defined in ADR-0013. Rather than instrument
Task() calls live, we read Claude Code's transcript JSONL (the runtime's own
system of record) and aggregate token totals onto framework discussions by
timestamp containment. The transcript path under ``~/.claude/projects/`` is
undocumented runtime state — the parser is therefore isolated behind a single
function (``parse_session_dir``) so any future path change is a one-file patch.

Usage:
    python scripts/ingest_token_usage.py             # scan all sessions
    python scripts/ingest_token_usage.py --dry-run   # report only, no writes
    python scripts/ingest_token_usage.py --since YYYY-MM-DD
    python scripts/ingest_token_usage.py --discussion DISC-...
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"

# Claude Code stores transcripts under ~/.claude/projects/<slug>/
# where <slug> is the project's absolute path with backslashes and colons
# replaced by dashes. This path is undocumented runtime state — keep all
# knowledge of it inside parse_session_dir / discover_session_dirs.
CLAUDE_PROJECTS_ROOT = Path.home() / ".claude" / "projects"


# ---------------------------------------------------------------------------
# Parser layer — isolated so a path/format change is a one-file patch.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MessageRecord:
    """A single token-usage record parsed from a Claude Code transcript line.

    Attributes:
        message_id: Anthropic API message id (e.g. ``msg_01ABC...``). Used for
            deduplication across main + subagent JSONLs.
        timestamp: ISO 8601 timestamp (timezone-aware UTC).
        model: Model identifier from the message, or ``None`` if absent.
        input_tokens: ``usage.input_tokens`` or ``None`` if absent.
        output_tokens: ``usage.output_tokens`` or ``None`` if absent.
        cache_read_tokens: ``usage.cache_read_input_tokens`` or ``None``.
        cache_create_tokens: ``usage.cache_creation_input_tokens`` or ``None``.
        source_file: The JSONL file this record was parsed from (for debugging).
    """

    message_id: str
    timestamp: datetime
    model: str | None
    input_tokens: int | None
    output_tokens: int | None
    cache_read_tokens: int | None
    cache_create_tokens: int | None
    source_file: Path


def _project_slug(project_root: Path) -> str:
    """Compute the Claude Code project slug from an absolute project path.

    Claude Code derives a per-project directory under ``~/.claude/projects/``
    by capitalising the drive letter, replacing ``:`` with ``--``, and
    replacing every other run of non-alphanumeric characters (path separators,
    spaces, underscores) with a single ``-``. Example::

        c:\\Work\\AI\\AI Gen Framework Research\\agent_framework_template
        -> C--Work-AI-AI-Gen-Framework-Research-agent-framework-template

    If discovery fails to find a match for the computed slug we also try a
    case-insensitive scan inside ``discover_session_dirs`` as a safety net.
    """
    import re

    abs_path = str(project_root.resolve())
    # Capitalise the leading drive letter (Windows convention) before any
    # separator-stripping, so the drive letter is preserved.
    if len(abs_path) >= 1 and abs_path[0].isalpha():
        abs_path = abs_path[0].upper() + abs_path[1:]
    # Treat the drive separator ':\' or ':/' as a single token mapping to '--',
    # then collapse every other run of non-alphanumeric characters into '-'.
    abs_path = re.sub(r":[\\/]+", "--", abs_path, count=1)
    return re.sub(r"[^A-Za-z0-9-]+", "-", abs_path)


def _is_inside_projects_root(path: Path) -> bool:
    """Return True iff the resolved path lives inside CLAUDE_PROJECTS_ROOT.

    Guards against symlink traversal — a symlinked entry inside the projects
    directory that points elsewhere on the filesystem is silently skipped.
    REVIEW.md rule 18 (file path operations must use Path.resolve() and
    validate against a whitelist of allowed directories).
    """
    try:
        return path.resolve().is_relative_to(CLAUDE_PROJECTS_ROOT.resolve())
    except OSError:
        return False


def discover_session_dirs(project_root: Path) -> list[Path]:
    """Return all session JSONL roots for the given project.

    Returns paths to scan. Each path may be either a session ``.jsonl`` file at
    the project root, or a session directory containing a ``subagents/``
    subdirectory with ``agent-*.jsonl`` files. Callers should pass the result
    to ``parse_session_dir``.

    Symlinked entries that resolve outside ``CLAUDE_PROJECTS_ROOT`` are
    skipped (see ``_is_inside_projects_root``).
    """
    if not CLAUDE_PROJECTS_ROOT.exists():
        return []
    slug = _project_slug(project_root)
    project_dir = CLAUDE_PROJECTS_ROOT / slug
    if not project_dir.exists():
        # Safety net: scan for a case-insensitive match in case Claude Code's
        # slug derivation changes drive-letter casing in a future version.
        target = slug.lower()
        match = next(
            (d for d in CLAUDE_PROJECTS_ROOT.iterdir() if d.is_dir() and d.name.lower() == target),
            None,
        )
        if match is None:
            return []
        project_dir = match
    if not _is_inside_projects_root(project_dir):
        return []
    paths: list[Path] = []
    for entry in project_dir.iterdir():
        if not _is_inside_projects_root(entry):
            continue
        if entry.is_file() and entry.suffix == ".jsonl":
            paths.append(entry)
        elif entry.is_dir():
            paths.append(entry)
    return paths


def _parse_timestamp(value: str) -> datetime | None:
    """Parse an ISO 8601 timestamp into a timezone-aware UTC datetime."""
    if not value:
        return None
    try:
        # JSONL uses trailing 'Z'; SQLite stores '+00:00'. Normalize both.
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except (ValueError, TypeError):
        return None


def _coerce_int(value: object) -> int | None:
    """Return ``int(value)`` if it is a non-negative integer, else ``None``."""
    if isinstance(value, bool):  # bools are ints in Python — exclude explicitly
        return None
    if isinstance(value, int):
        return value
    return None


def _parse_message_line(line: str, source_file: Path) -> MessageRecord | None:
    """Parse a single JSONL line into a MessageRecord, or ``None`` to skip.

    Lines without a ``message.id`` (e.g. queue-operation, system events) are
    skipped — only assistant message records carry token usage.
    """
    line = line.strip()
    if not line:
        return None
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        return None
    message = record.get("message")
    if not isinstance(message, dict):
        return None
    message_id = message.get("id")
    if not isinstance(message_id, str) or not message_id:
        return None
    ts = _parse_timestamp(record.get("timestamp", ""))
    if ts is None:
        return None
    usage = message.get("usage") or {}
    if not isinstance(usage, dict):
        usage = {}
    return MessageRecord(
        message_id=message_id,
        timestamp=ts,
        model=message.get("model") if isinstance(message.get("model"), str) else None,
        input_tokens=_coerce_int(usage.get("input_tokens")),
        output_tokens=_coerce_int(usage.get("output_tokens")),
        cache_read_tokens=_coerce_int(usage.get("cache_read_input_tokens")),
        cache_create_tokens=_coerce_int(usage.get("cache_creation_input_tokens")),
        source_file=source_file,
    )


def _iter_jsonl_files(path: Path) -> Iterator[Path]:
    """Yield JSONL files reachable from a session path.

    Accepts either a single ``.jsonl`` file (main session at project root) or
    a session directory containing a ``subagents/`` subdirectory. Hidden and
    non-JSONL files are ignored. Entries that resolve outside
    ``CLAUDE_PROJECTS_ROOT`` (symlink escape) are skipped.
    """
    if not _is_inside_projects_root(path):
        return
    if path.is_file() and path.suffix == ".jsonl":
        yield path
        return
    if not path.is_dir():
        return
    subagents = path / "subagents"
    if subagents.is_dir() and _is_inside_projects_root(subagents):
        for entry in subagents.iterdir():
            if entry.is_file() and entry.suffix == ".jsonl" and _is_inside_projects_root(entry):
                yield entry
    # Some session dirs may also contain a top-level <sessionId>.jsonl —
    # scan for any .jsonl directly under the dir as well.
    for entry in path.iterdir():
        if entry.is_file() and entry.suffix == ".jsonl" and _is_inside_projects_root(entry):
            yield entry


def parse_session_dir(path: Path) -> Iterator[MessageRecord]:
    """Yield MessageRecord values for every parseable line under ``path``.

    Args:
        path: Either a session ``.jsonl`` file or a session directory. The
            caller obtains these paths from ``discover_session_dirs``.

    Yields:
        One MessageRecord per parseable assistant message. Lines lacking a
        ``message.id`` or a timestamp are silently skipped (they are system
        events, user echoes, or malformed entries).
    """
    for jsonl_path in _iter_jsonl_files(path):
        try:
            with open(jsonl_path, encoding="utf-8") as handle:
                for line in handle:
                    record = _parse_message_line(line, jsonl_path)
                    if record is not None:
                        yield record
        except OSError:
            continue


# ---------------------------------------------------------------------------
# Schema migration — defensive, idempotent.
# ---------------------------------------------------------------------------


def _ensure_token_columns(conn: sqlite3.Connection) -> None:
    """Add token columns to ``turns`` and ``discussions`` if missing.

    Mirrors the migration pattern in ``init_db.py``: wraps each ALTER TABLE in
    a try/except so the call is safe to repeat. Required so this script can
    run against a database that pre-dates the ADR-0013 schema bump.
    """
    migrations = [
        ("turns", "tokens_in", "INTEGER"),
        ("turns", "tokens_out", "INTEGER"),
        ("turns", "cache_read_tokens", "INTEGER"),
        ("turns", "cache_create_tokens", "INTEGER"),
        ("discussions", "total_tokens_in", "INTEGER"),
        ("discussions", "total_tokens_out", "INTEGER"),
        ("discussions", "total_cache_tokens", "INTEGER"),
    ]
    for table, column, col_type in migrations:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        except sqlite3.OperationalError:
            pass  # Column already exists
    conn.commit()


# ---------------------------------------------------------------------------
# Attribution + write layer.
# ---------------------------------------------------------------------------


@dataclass
class DiscussionWindow:
    """A discussion's active window for timestamp attribution."""

    discussion_id: str
    start: datetime
    end: datetime  # closed_at, or now() if still open


def _load_discussion_windows(
    conn: sqlite3.Connection, discussion_filter: str | None
) -> list[DiscussionWindow]:
    """Load discussion windows from SQLite, optionally restricted to one id."""
    if discussion_filter:
        rows = conn.execute(
            "SELECT discussion_id, created_at, closed_at FROM discussions WHERE discussion_id = ?",
            (discussion_filter,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT discussion_id, created_at, closed_at FROM discussions"
        ).fetchall()
    windows: list[DiscussionWindow] = []
    now = datetime.now(UTC)
    for discussion_id, created_at, closed_at in rows:
        start = _parse_timestamp(created_at) if created_at else None
        if start is None:
            continue
        end = _parse_timestamp(closed_at) if closed_at else now
        if end is None:
            end = now
        windows.append(DiscussionWindow(discussion_id, start, end))
    # Sort newest-first so the typical lookup hits early.
    windows.sort(key=lambda w: w.start, reverse=True)
    return windows


def _attribute(message: MessageRecord, windows: list[DiscussionWindow]) -> str | None:
    """Return the discussion_id whose window contains the message timestamp."""
    for window in windows:
        if window.start <= message.timestamp <= window.end:
            return window.discussion_id
    return None


def _sum_int(values: list[int | None]) -> int | None:
    """Sum a list of optional ints; ``None`` if all entries are ``None``."""
    present = [v for v in values if v is not None]
    if not present:
        return None
    return sum(present)


def _aggregate_by_discussion(
    messages: dict[str, MessageRecord], windows: list[DiscussionWindow]
) -> dict[str, dict[str, int | None]]:
    """Group dedup'd messages by discussion and sum token columns.

    Returns:
        Mapping from discussion_id to a dict with keys ``total_tokens_in``,
        ``total_tokens_out``, ``total_cache_tokens``, and ``message_count``.
    """
    buckets: dict[str, dict[str, list[int | None]]] = {}
    for message in messages.values():
        discussion_id = _attribute(message, windows)
        if discussion_id is None:
            continue
        bucket = buckets.setdefault(
            discussion_id,
            {"in": [], "out": [], "cache": [], "_count": []},
        )
        bucket["in"].append(message.input_tokens)
        bucket["out"].append(message.output_tokens)
        # Combine cache read + create into total_cache_tokens.
        cache_components = [
            message.cache_read_tokens,
            message.cache_create_tokens,
        ]
        cache_sum = _sum_int(cache_components)
        bucket["cache"].append(cache_sum)
        bucket["_count"].append(1)
    aggregated: dict[str, dict[str, int | None]] = {}
    for discussion_id, bucket in buckets.items():
        aggregated[discussion_id] = {
            "total_tokens_in": _sum_int(bucket["in"]),
            "total_tokens_out": _sum_int(bucket["out"]),
            "total_cache_tokens": _sum_int(bucket["cache"]),
            "message_count": len(bucket["_count"]),
        }
    return aggregated


def _write_discussion_totals(
    conn: sqlite3.Connection, totals: dict[str, dict[str, int | None]]
) -> None:
    """Write aggregated totals back to the ``discussions`` table.

    Uses idempotent UPDATE — running again with the same data produces the
    same row state. NULLs are written as NULL, never zero-filled.
    """
    for discussion_id, fields in totals.items():
        conn.execute(
            """UPDATE discussions
               SET total_tokens_in = ?,
                   total_tokens_out = ?,
                   total_cache_tokens = ?
               WHERE discussion_id = ?""",
            (
                fields["total_tokens_in"],
                fields["total_tokens_out"],
                fields["total_cache_tokens"],
                discussion_id,
            ),
        )
    conn.commit()


def _update_tagged_turns(conn: sqlite3.Connection, messages: dict[str, MessageRecord]) -> int:
    """Opportunistically update per-turn token columns where tagged.

    A turn is updated only when its ``tags`` column contains a literal
    substring ``message-id:<id>`` matching a parsed message. This is a future
    hook — the Task() wrapper does not yet tag turns this way, so this
    function is expected to return 0 today.
    """
    updated = 0
    for message_id, message in messages.items():
        tag_token = f"message-id:{message_id}"
        rows = conn.execute(
            "SELECT id FROM turns WHERE tags LIKE ?",
            (f"%{tag_token}%",),
        ).fetchall()
        for (row_id,) in rows:
            conn.execute(
                """UPDATE turns
                   SET tokens_in = ?,
                       tokens_out = ?,
                       cache_read_tokens = ?,
                       cache_create_tokens = ?
                   WHERE id = ?""",
                (
                    message.input_tokens,
                    message.output_tokens,
                    message.cache_read_tokens,
                    message.cache_create_tokens,
                    row_id,
                ),
            )
            updated += 1
    conn.commit()
    return updated


# ---------------------------------------------------------------------------
# Orchestration.
# ---------------------------------------------------------------------------


def _collect_messages(
    session_paths: list[Path], since: datetime | None
) -> dict[str, MessageRecord]:
    """Walk every session path and return a dedup'd message_id → record map.

    A message that appears in both a main session JSONL and a subagent JSONL
    is counted exactly once (first occurrence wins).
    """
    deduped: dict[str, MessageRecord] = {}
    for path in session_paths:
        for record in parse_session_dir(path):
            if since is not None and record.timestamp < since:
                continue
            if record.message_id in deduped:
                continue
            deduped[record.message_id] = record
    return deduped


def ingest_token_usage(
    *,
    dry_run: bool = False,
    since: datetime | None = None,
    discussion_filter: str | None = None,
) -> dict[str, int]:
    """Run the full ingest pipeline.

    Args:
        dry_run: If True, compute and report but do not write to SQLite.
        since: If provided, ignore messages with timestamp earlier than this.
        discussion_filter: If provided, only attribute to this discussion.

    Returns:
        A summary dict with keys ``sessions``, ``messages_seen``,
        ``messages_attributed``, ``discussions_updated``, ``turns_updated``,
        ``total_tokens_in``, ``total_tokens_out``, ``total_cache_tokens``.
    """
    if not CLAUDE_PROJECTS_ROOT.exists():
        print(
            f"Claude Code transcript root not found: {CLAUDE_PROJECTS_ROOT}. "
            "Nothing to ingest — exiting cleanly."
        )
        return {
            "sessions": 0,
            "messages_seen": 0,
            "messages_attributed": 0,
            "discussions_updated": 0,
            "turns_updated": 0,
            "total_tokens_in": 0,
            "total_tokens_out": 0,
            "total_cache_tokens": 0,
        }

    session_paths = discover_session_dirs(PROJECT_ROOT)
    if not session_paths:
        print(
            f"No session transcripts for project slug "
            f"'{_project_slug(PROJECT_ROOT)}' under {CLAUDE_PROJECTS_ROOT}."
        )
        return {
            "sessions": 0,
            "messages_seen": 0,
            "messages_attributed": 0,
            "discussions_updated": 0,
            "turns_updated": 0,
            "total_tokens_in": 0,
            "total_tokens_out": 0,
            "total_cache_tokens": 0,
        }

    messages = _collect_messages(session_paths, since)

    if not DB_PATH.exists():
        print(f"SQLite database not found at {DB_PATH}. Run scripts/init_db.py first.")
        return {
            "sessions": len(session_paths),
            "messages_seen": len(messages),
            "messages_attributed": 0,
            "discussions_updated": 0,
            "turns_updated": 0,
            "total_tokens_in": 0,
            "total_tokens_out": 0,
            "total_cache_tokens": 0,
        }

    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        _ensure_token_columns(conn)
        windows = _load_discussion_windows(conn, discussion_filter)
        totals = _aggregate_by_discussion(messages, windows)

        attributed_count = sum(t["message_count"] or 0 for t in totals.values())
        sum_in = sum((t["total_tokens_in"] or 0) for t in totals.values())
        sum_out = sum((t["total_tokens_out"] or 0) for t in totals.values())
        sum_cache = sum((t["total_cache_tokens"] or 0) for t in totals.values())

        turns_updated = 0
        if not dry_run:
            _write_discussion_totals(conn, totals)
            turns_updated = _update_tagged_turns(conn, messages)
    finally:
        conn.close()

    return {
        "sessions": len(session_paths),
        "messages_seen": len(messages),
        "messages_attributed": attributed_count,
        "discussions_updated": len(totals),
        "turns_updated": turns_updated,
        "total_tokens_in": sum_in,
        "total_tokens_out": sum_out,
        "total_cache_tokens": sum_cache,
    }


def _parse_since(value: str | None) -> datetime | None:
    """Parse a ``--since YYYY-MM-DD`` argument to a UTC datetime."""
    if not value:
        return None
    try:
        dt = datetime.strptime(value, "%Y-%m-%d")
        return dt.replace(tzinfo=UTC)
    except ValueError as exc:
        raise SystemExit(f"--since must be YYYY-MM-DD ({exc})") from exc


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest Claude Code token usage into SQLite (ADR-0013)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be written but do not modify the database.",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="Only consider messages on/after this date (YYYY-MM-DD, UTC).",
    )
    parser.add_argument(
        "--discussion",
        default=None,
        help="Attribute messages only to this discussion id.",
    )
    args = parser.parse_args()

    summary = ingest_token_usage(
        dry_run=args.dry_run,
        since=_parse_since(args.since),
        discussion_filter=args.discussion,
    )

    prefix = "[dry-run] " if args.dry_run else ""
    print(
        f"{prefix}Scanned {summary['sessions']} session path(s); "
        f"saw {summary['messages_seen']} unique message(s); "
        f"attributed {summary['messages_attributed']} to "
        f"{summary['discussions_updated']} discussion(s); "
        f"updated {summary['turns_updated']} tagged turn(s)."
    )
    print(
        f"{prefix}Ingested {summary['messages_attributed']} messages into "
        f"{summary['discussions_updated']} discussions "
        f"({summary['total_tokens_in']} tokens in, "
        f"{summary['total_tokens_out']} tokens out, "
        f"{summary['total_cache_tokens']} cache)."
    )


if __name__ == "__main__":
    main()
