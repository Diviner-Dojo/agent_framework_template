"""Tests for scripts/ingest_token_usage.py.

Covers the ADR-0013 post-hoc token ingestion pipeline: JSONL parsing,
timestamp-based attribution to discussion windows, dedup contract, idempotency,
and honest-NULL aggregation semantics.

The production module reads transcripts from ``~/.claude/projects/`` and writes
to ``metrics/evaluation.db`` — both paths are monkeypatched to ``tmp_path`` in
every integration-flavored test so we never touch real runtime state.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.ingest_token_usage import (
    DiscussionWindow,
    MessageRecord,
    _aggregate_by_discussion,
    _attribute,
    _collect_messages,
    _parse_message_line,
    _project_slug,
    coerce_int,
    ingest_token_usage,
    load_discussion_windows,
    parse_timestamp,
)
from scripts.init_db import init_db

# ---------------------------------------------------------------------------
# Pure helpers.
# ---------------------------------------------------------------------------


class TestProjectSlug:
    """Verify _project_slug produces the Claude Code slug shape."""

    def test_windows_path_shape(self, tmp_path: Path) -> None:
        """A Windows-style path produces the expected drive-letter-prefixed slug.

        We can't pass an arbitrary string — ``resolve()`` is called inside the
        function — so we exercise it on a real ``tmp_path`` and assert on the
        slug's *shape* rather than a hard-coded value.
        """
        slug = _project_slug(tmp_path)
        # Drive letter uppercased, ':\' becomes '--', no other non-alphanumeric
        # chars survive (collapsed to single '-').
        assert "--" in slug, f"Expected '--' separator in slug, got: {slug}"
        # Everything is uppercase letter, digit, or dash.
        assert all(c.isalnum() or c == "-" for c in slug), (
            f"Slug contains unexpected chars: {slug}"
        )
        # Leading char is the uppercased drive letter.
        assert slug[0].isupper()


# ---------------------------------------------------------------------------
# _parse_message_line — parametrized coverage of valid + every reject path.
# ---------------------------------------------------------------------------


def _make_jsonl_line(
    *,
    message_id: str | None = "msg_01ABC",
    timestamp: str | None = "2026-01-01T12:00:00Z",
    usage: dict | None = None,
    model: str = "claude-opus-4-7",
    include_message: bool = True,
    include_message_id: bool = True,
) -> str:
    """Construct one valid JSONL line, with optional fields removed for failure cases."""
    if usage is None:
        usage = {
            "input_tokens": 100,
            "output_tokens": 200,
            "cache_read_input_tokens": 50,
            "cache_creation_input_tokens": 10,
        }
    message: dict = {"model": model, "usage": usage}
    if include_message_id and message_id is not None:
        message["id"] = message_id
    record: dict = {}
    if include_message:
        record["message"] = message
    if timestamp is not None:
        record["timestamp"] = timestamp
    return json.dumps(record)


class TestParseMessageLine:
    """Parametrized coverage of _parse_message_line success and reject paths."""

    def test_valid_full_usage(self, tmp_path: Path) -> None:
        """A well-formed line with full usage block parses into a MessageRecord."""
        source = tmp_path / "session.jsonl"
        line = _make_jsonl_line()
        rec = _parse_message_line(line, source)
        assert rec is not None
        assert rec.message_id == "msg_01ABC"
        assert rec.timestamp == datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        assert rec.input_tokens == 100
        assert rec.output_tokens == 200
        assert rec.cache_read_tokens == 50
        assert rec.cache_create_tokens == 10
        assert rec.model == "claude-opus-4-7"
        assert rec.source_file == source

    @pytest.mark.parametrize(
        "line",
        [
            "this is not json",
            "{not valid",
            '{"message": {"id": "x"}, "timestamp": "2026-01-01T00:00:00Z"',  # truncated
        ],
    )
    def test_malformed_json_returns_none(self, tmp_path: Path, line: str) -> None:
        """Any JSON parse failure yields None (skipped silently)."""
        assert _parse_message_line(line, tmp_path / "x.jsonl") is None

    def test_no_message_key_returns_none(self, tmp_path: Path) -> None:
        """A record lacking a top-level 'message' key is skipped."""
        line = json.dumps({"timestamp": "2026-01-01T00:00:00Z", "type": "system"})
        assert _parse_message_line(line, tmp_path / "x.jsonl") is None

    def test_missing_message_id_returns_none(self, tmp_path: Path) -> None:
        """A 'message' record without an 'id' is skipped."""
        line = _make_jsonl_line(include_message_id=False)
        assert _parse_message_line(line, tmp_path / "x.jsonl") is None

    def test_missing_timestamp_returns_none(self, tmp_path: Path) -> None:
        """A record without a top-level timestamp is skipped."""
        line = _make_jsonl_line(timestamp=None)
        assert _parse_message_line(line, tmp_path / "x.jsonl") is None

    def test_missing_input_tokens_returns_none_not_zero(self, tmp_path: Path) -> None:
        """When usage.input_tokens is absent, input_tokens is None (honest NULL).

        This is the contract that ADR-0013 leans on: a missing value must not
        be zero-filled, because the downstream aggregator treats None as
        "unknown" and 0 as "known-zero".
        """
        line = _make_jsonl_line(
            usage={
                "output_tokens": 50,
                "cache_read_input_tokens": 5,
                "cache_creation_input_tokens": 1,
            }
        )
        rec = _parse_message_line(line, tmp_path / "x.jsonl")
        assert rec is not None
        assert rec.input_tokens is None
        assert rec.output_tokens == 50

    def test_bool_input_tokens_returns_none(self, tmp_path: Path) -> None:
        """A bool ``True`` in usage.input_tokens is rejected by coerce_int.

        Python's ``bool`` is a subclass of ``int`` — the guard at the top of
        ``coerce_int`` exists specifically to reject this case so a JSON
        ``true`` value cannot be silently coerced to 1.
        """
        line = _make_jsonl_line(
            usage={
                "input_tokens": True,
                "output_tokens": 200,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            }
        )
        rec = _parse_message_line(line, tmp_path / "x.jsonl")
        assert rec is not None
        assert rec.input_tokens is None
        # Other fields unaffected.
        assert rec.output_tokens == 200


# ---------------------------------------------------------------------------
# _attribute — boundary cases against a two-window list (newest-first sort).
# ---------------------------------------------------------------------------


@pytest.fixture()
def two_windows() -> list[DiscussionWindow]:
    """Two non-overlapping discussion windows, sorted newest-first.

    Window A: 2026-02-01 10:00 .. 2026-02-01 11:00 (older)
    Window B: 2026-02-02 10:00 .. 2026-02-02 11:00 (newer, listed first)
    """
    a = DiscussionWindow(
        discussion_id="DISC-A",
        start=datetime(2026, 2, 1, 10, 0, 0, tzinfo=UTC),
        end=datetime(2026, 2, 1, 11, 0, 0, tzinfo=UTC),
    )
    b = DiscussionWindow(
        discussion_id="DISC-B",
        start=datetime(2026, 2, 2, 10, 0, 0, tzinfo=UTC),
        end=datetime(2026, 2, 2, 11, 0, 0, tzinfo=UTC),
    )
    # newest-first: B before A
    return [b, a]


def _msg_at(ts: datetime) -> MessageRecord:
    """Build a MessageRecord with the given timestamp (other fields are stubs)."""
    return MessageRecord(
        message_id="msg_x",
        timestamp=ts,
        model="claude-opus-4-7",
        input_tokens=1,
        output_tokens=1,
        cache_read_tokens=0,
        cache_create_tokens=0,
        source_file=Path("/tmp/x.jsonl"),
    )


class TestAttribute:
    """Verify boundary inclusivity and miss behavior for _attribute."""

    def test_timestamp_equals_window_start(self, two_windows: list[DiscussionWindow]) -> None:
        """A timestamp exactly equal to window.start attributes to that window."""
        msg = _msg_at(datetime(2026, 2, 1, 10, 0, 0, tzinfo=UTC))
        assert _attribute(msg, two_windows) == "DISC-A"

    def test_timestamp_equals_window_end(self, two_windows: list[DiscussionWindow]) -> None:
        """A timestamp exactly equal to window.end attributes to that window."""
        msg = _msg_at(datetime(2026, 2, 1, 11, 0, 0, tzinfo=UTC))
        assert _attribute(msg, two_windows) == "DISC-A"

    def test_timestamp_before_all_windows(self, two_windows: list[DiscussionWindow]) -> None:
        """A timestamp strictly before all windows yields None."""
        msg = _msg_at(datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC))
        assert _attribute(msg, two_windows) is None

    def test_timestamp_after_all_windows(self, two_windows: list[DiscussionWindow]) -> None:
        """A timestamp strictly after all windows yields None."""
        msg = _msg_at(datetime(2026, 3, 1, 0, 0, 0, tzinfo=UTC))
        assert _attribute(msg, two_windows) is None

    def test_timestamp_inside_window(self, two_windows: list[DiscussionWindow]) -> None:
        """A timestamp inside window B attributes to B."""
        msg = _msg_at(datetime(2026, 2, 2, 10, 30, 0, tzinfo=UTC))
        assert _attribute(msg, two_windows) == "DISC-B"

    def test_deterministic_single_match(self, two_windows: list[DiscussionWindow]) -> None:
        """With newest-first sort, a timestamp matching exactly one window picks that one.

        Window B is listed first; the message is inside window A. The function
        must walk past B and return A — not stop at B or return ambiguously.
        """
        msg = _msg_at(datetime(2026, 2, 1, 10, 30, 0, tzinfo=UTC))
        assert _attribute(msg, two_windows) == "DISC-A"


# ---------------------------------------------------------------------------
# _collect_messages — first-wins dedup contract.
# ---------------------------------------------------------------------------


class TestCollectMessages:
    """Verify dedup behavior across multiple JSONL files."""

    def test_first_wins_across_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two files contain the same message id; the first iterated wins.

        This documents the deterministic dedup contract — important because the
        same ``msg_*`` id can appear in both the main session JSONL and a
        subagent JSONL, and we must not double-count tokens.

        Establishes ``tmp_path`` as the trust root for ``_is_inside_projects_root``
        so the symlink-traversal guard doesn't reject the test fixtures.
        """
        monkeypatch.setattr("scripts.ingest_token_usage.CLAUDE_PROJECTS_ROOT", tmp_path)
        path1 = tmp_path / "session_a.jsonl"
        path2 = tmp_path / "session_b.jsonl"
        # Same message id, different output_tokens — first wins.
        path1.write_text(
            _make_jsonl_line(
                message_id="msg_dup", usage={"input_tokens": 10, "output_tokens": 111}
            )
            + "\n",
            encoding="utf-8",
        )
        path2.write_text(
            _make_jsonl_line(
                message_id="msg_dup", usage={"input_tokens": 10, "output_tokens": 999}
            )
            + "\n",
            encoding="utf-8",
        )

        result = _collect_messages([path1, path2], since=None)
        assert len(result) == 1
        assert "msg_dup" in result
        # path1 was iterated first, so its output_tokens (111) wins.
        assert result["msg_dup"].output_tokens == 111


# ---------------------------------------------------------------------------
# _aggregate_by_discussion — honest NULL semantic.
# ---------------------------------------------------------------------------


class TestAggregateHonestNull:
    """When every attributed message has input_tokens=None, the sum is None, not 0."""

    def test_all_none_input_tokens_yields_null_total(
        self, two_windows: list[DiscussionWindow]
    ) -> None:
        """All-None input column rolls up to None (honest NULL)."""
        # Two messages both inside window A, both with input_tokens=None.
        msgs: dict[str, MessageRecord] = {}
        for i, mid in enumerate(["m1", "m2"]):
            msgs[mid] = MessageRecord(
                message_id=mid,
                timestamp=datetime(2026, 2, 1, 10, 15 + i, 0, tzinfo=UTC),
                model="claude-opus-4-7",
                input_tokens=None,
                output_tokens=200 + i,
                cache_read_tokens=None,
                cache_create_tokens=None,
                source_file=Path("/tmp/x.jsonl"),
            )
        agg = _aggregate_by_discussion(msgs, two_windows)
        assert "DISC-A" in agg
        # input is all-None -> None, not 0
        assert agg["DISC-A"]["total_tokens_in"] is None
        # output has values -> a real sum
        assert agg["DISC-A"]["total_tokens_out"] == 401
        # cache columns are all None -> None
        assert agg["DISC-A"]["total_cache_tokens"] is None


# ---------------------------------------------------------------------------
# Idempotency — end-to-end against monkeypatched paths.
# ---------------------------------------------------------------------------


def _setup_fake_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path]:
    """Point CLAUDE_PROJECTS_ROOT, PROJECT_ROOT, and DB_PATH at tmp_path.

    Returns:
        (db_path, project_dir) — caller writes JSONL into project_dir.
    """
    # Fake project root — its resolve() result drives _project_slug.
    fake_proj = tmp_path / "fake_project"
    fake_proj.mkdir()

    # Fake transcripts root.
    claude_root = tmp_path / "claude_projects"
    claude_root.mkdir()

    # We need the slug to MATCH what _project_slug(fake_proj) computes —
    # easiest path is to compute it ourselves then create that directory.
    slug = _project_slug(fake_proj)
    project_dir = claude_root / slug
    project_dir.mkdir()

    # Fake DB path.
    db_path = tmp_path / "evaluation.db"

    monkeypatch.setattr("scripts.ingest_token_usage.CLAUDE_PROJECTS_ROOT", claude_root)
    monkeypatch.setattr("scripts.ingest_token_usage.PROJECT_ROOT", fake_proj)
    monkeypatch.setattr("scripts.ingest_token_usage.DB_PATH", db_path)
    return db_path, project_dir


class TestIngestIdempotency:
    """Running ingest_token_usage twice produces identical discussions.total_* rows."""

    def test_two_runs_equal(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Second invocation yields the same totals as the first."""
        db_path, project_dir = _setup_fake_runtime(monkeypatch, tmp_path)
        init_db(db_path)

        # Insert one open discussion whose window covers our message timestamp.
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(
            "INSERT INTO discussions "
            "(discussion_id, created_at, closed_at, risk_level, "
            "collaboration_mode, status, agent_count) "
            "VALUES (?, ?, ?, 'low', 'ensemble', 'closed', 0)",
            ("DISC-IDEMP", "2026-01-01T00:00:00+00:00", "2026-01-01T23:59:59+00:00"),
        )
        conn.commit()
        conn.close()

        # Write one JSONL file with two messages inside the window.
        jsonl = project_dir / "session.jsonl"
        lines = [
            _make_jsonl_line(
                message_id="msg_1",
                timestamp="2026-01-01T10:00:00Z",
                usage={
                    "input_tokens": 100,
                    "output_tokens": 200,
                    "cache_read_input_tokens": 5,
                    "cache_creation_input_tokens": 10,
                },
            ),
            _make_jsonl_line(
                message_id="msg_2",
                timestamp="2026-01-01T11:00:00Z",
                usage={
                    "input_tokens": 50,
                    "output_tokens": 75,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                },
            ),
        ]
        jsonl.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # Run twice, capture row state after each.
        def _snapshot() -> tuple:
            c = sqlite3.connect(str(db_path))
            row = c.execute(
                "SELECT total_tokens_in, total_tokens_out, total_cache_tokens "
                "FROM discussions WHERE discussion_id = ?",
                ("DISC-IDEMP",),
            ).fetchone()
            c.close()
            return row

        ingest_token_usage(dry_run=False)
        snap1 = _snapshot()
        ingest_token_usage(dry_run=False)
        snap2 = _snapshot()

        assert snap1 == snap2
        # Sanity: actually wrote sums (not all None).
        assert snap1 == (150, 275, 15)


# ---------------------------------------------------------------------------
# Public helper contract — these were promoted from private (Rule of Three:
# reused by scripts/telemetry/analyze_cost.py + analyze_failures.py). Lock the
# public names so a future re-privatization breaks loudly here, not silently at
# a cross-module caller.
# ---------------------------------------------------------------------------


class TestPublicHelperContract:
    """Verify the promoted helpers are public API and still behave."""

    def test_coerce_int_accepts_int_rejects_bool_and_nonint(self) -> None:
        """coerce_int keeps ints, excludes bool (an int subclass), rejects others."""
        assert coerce_int(5) == 5
        assert coerce_int(0) == 0
        assert coerce_int(True) is None  # bool is an int subclass — excluded
        assert coerce_int("5") is None
        assert coerce_int(None) is None

    def test_parse_timestamp_normalizes_z_suffix_to_utc(self) -> None:
        """parse_timestamp maps a trailing 'Z' to a tz-aware UTC datetime."""
        dt = parse_timestamp("2026-02-01T10:00:00Z")
        assert dt == datetime(2026, 2, 1, 10, 0, 0, tzinfo=UTC)
        assert parse_timestamp("") is None
        assert parse_timestamp("not-a-date") is None

    def test_load_discussion_windows_reads_open_and_closed(self, tmp_path: Path) -> None:
        """load_discussion_windows reads windows; closed_at bounds a closed one."""
        db_path = tmp_path / "evaluation.db"
        init_db(db_path, quiet=True)  # also exercises the quiet=True path
        conn = sqlite3.connect(str(db_path))
        try:
            conn.executemany(
                "INSERT INTO discussions (discussion_id, created_at, closed_at, "
                "risk_level, collaboration_mode) VALUES (?, ?, ?, 'low', 'ensemble')",
                [
                    ("DISC-OPEN", "2026-02-01T10:00:00+00:00", None),
                    ("DISC-CLOSED", "2026-02-02T10:00:00+00:00", "2026-02-02T11:00:00+00:00"),
                ],
            )
            conn.commit()
            windows = load_discussion_windows(conn, None)
        finally:
            conn.close()
        by_id = {w.discussion_id: w for w in windows}
        assert set(by_id) == {"DISC-OPEN", "DISC-CLOSED"}
        # Open discussion: end defaults to ~now, so it is at/after its start.
        assert by_id["DISC-OPEN"].end >= by_id["DISC-OPEN"].start
        # Closed discussion: end is exactly its closed_at.
        assert by_id["DISC-CLOSED"].end == datetime(2026, 2, 2, 11, 0, 0, tzinfo=UTC)
