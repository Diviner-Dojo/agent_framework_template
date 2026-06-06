"""Tests for telemetry Layer A1 — per-tier cost + coverage.

Pure-logic tests (pricing resolution, cost aggregation, coverage denominator)
plus integration tests for the analyzer that NEVER touch the live ~/.claude
directory — the transcript root and project root are monkeypatched onto the
reused ``ingest_token_usage`` module and the DB path is a ``tmp_path`` SQLite.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest

from scripts import ingest_token_usage as itu
from scripts.init_db import init_db
from scripts.telemetry import analyze_cost as ac
from scripts.telemetry import analyze_failures as af
from src.telemetry.cost import ModelTokenRow, build_cost_report
from src.telemetry.failures import (
    FailureSignal,
    SubagentDispatch,
    SubagentRun,
    ToolCall,
    detect_orphaned_subagents,
    detect_retry_loops,
    rank_failures,
)
from src.telemetry.pricing import (
    UNKNOWN_TIER,
    PricingTable,
    load_pricing,
    parse_pricing,
)

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

PRICING_DATA = {
    "tiers": {
        "opus": {
            "input": 15.0,
            "output": 75.0,
            "cache_read_multiplier": 0.1,
            "cache_create_multiplier": 1.25,
        },
        "sonnet": {
            "input": 3.0,
            "output": 15.0,
            "cache_read_multiplier": 0.1,
            "cache_create_multiplier": 1.25,
        },
    },
    "models": {"claude-opus-4-7": "opus", "claude-sonnet-4-6": "sonnet"},
}


@pytest.fixture
def pricing() -> PricingTable:
    return parse_pricing(PRICING_DATA)


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "evaluation.db"
    init_db(db_path)
    return db_path


def _insert_discussion(
    db_path: Path,
    discussion_id: str,
    created_at: str,
    closed_at: str | None,
    status: str = "closed",
) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """INSERT INTO discussions
               (discussion_id, created_at, closed_at, risk_level,
                collaboration_mode, status)
               VALUES (?, ?, ?, 'medium', 'structured-dialogue', ?)""",
            (discussion_id, created_at, closed_at, status),
        )
        conn.commit()
    finally:
        conn.close()


def _write_transcript(projects_root: Path, project_root: Path, lines: list[str]) -> None:
    """Create a Claude-Code-style session JSONL for ``project_root``."""
    slug = itu._project_slug(project_root)
    session_dir = projects_root / slug
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "session.jsonl").write_text("\n".join(lines), encoding="utf-8")


def _msg_line(
    message_id: str,
    timestamp: str,
    model: str | None,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read: int = 0,
    cache_create: int = 0,
) -> str:
    message: dict = {
        "id": message_id,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_input_tokens": cache_read,
            "cache_creation_input_tokens": cache_create,
        },
    }
    if model is not None:
        message["model"] = model
    return json.dumps({"timestamp": timestamp, "message": message})


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Wire an isolated transcript root + project root + DB.

    Returns an object with ``db_path``, ``project_root``, ``projects_root`` and
    helpers so tests never read live ~/.claude.
    """
    projects_root = tmp_path / "claude_projects"
    projects_root.mkdir()
    project_root = tmp_path / "proj"
    project_root.mkdir()
    monkeypatch.setattr(itu, "CLAUDE_PROJECTS_ROOT", projects_root)
    monkeypatch.setattr(itu, "PROJECT_ROOT", project_root)
    db_path = _make_db(tmp_path)

    class Env:
        pass

    e = Env()
    e.db_path = db_path
    e.project_root = project_root
    e.projects_root = projects_root
    return e


# --------------------------------------------------------------------------- #
# pricing.py — pure
# --------------------------------------------------------------------------- #


def test_resolve_tier_exact_match(pricing: PricingTable) -> None:
    assert pricing.resolve_tier("claude-opus-4-7") == "opus"
    assert pricing.resolve_tier("claude-sonnet-4-6") == "sonnet"


def test_resolve_tier_family_substring(pricing: PricingTable) -> None:
    # Not in the models map, but the family name resolves the tier.
    assert pricing.resolve_tier("claude-opus-4-8") == "opus"
    assert pricing.resolve_tier("CLAUDE-SONNET-9-9") == "sonnet"


def test_resolve_tier_unknown(pricing: PricingTable) -> None:
    assert pricing.resolve_tier(None) == UNKNOWN_TIER
    assert pricing.resolve_tier("") == UNKNOWN_TIER
    assert pricing.resolve_tier("gpt-4o") == UNKNOWN_TIER
    # Family present in id but tier missing from table -> unknown.
    assert pricing.resolve_tier("claude-haiku-4-5") == UNKNOWN_TIER


def test_cost_usd_math(pricing: PricingTable) -> None:
    # 1M input @ $15 + 1M output @ $75 = $90 exactly.
    cost = pricing.cost_usd("opus", tokens_in=1_000_000, tokens_out=1_000_000)
    assert cost == pytest.approx(90.0)


def test_cost_usd_cache_multipliers(pricing: PricingTable) -> None:
    # cache_read priced at 0.1x input, cache_create at 1.25x input.
    cost = pricing.cost_usd("opus", cache_read_tokens=1_000_000, cache_create_tokens=1_000_000)
    assert cost == pytest.approx(15.0 * 0.1 + 15.0 * 1.25)


def test_cost_usd_unknown_tier_is_none(pricing: PricingTable) -> None:
    assert pricing.cost_usd(UNKNOWN_TIER, tokens_in=1_000) is None
    assert pricing.cost_usd("nonexistent", tokens_in=1_000) is None


def test_parse_pricing_malformed_degrades() -> None:
    # Missing/!dict sections degrade to empty, never raise.
    assert parse_pricing({}).tiers == {}
    assert parse_pricing({"tiers": "oops", "models": 5}).models == {}
    # A non-dict tier spec is skipped rather than crashing.
    table = parse_pricing({"tiers": {"opus": "bad", "sonnet": {"input": 3}}, "models": {}})
    assert "opus" not in table.tiers
    assert table.tiers["sonnet"].input == 3.0


def test_load_pricing_missing_file(tmp_path: Path) -> None:
    table = load_pricing(tmp_path / "nope.yaml")
    assert table.tiers == {}
    assert table.resolve_tier("claude-opus-4-7") == UNKNOWN_TIER


def test_load_pricing_bad_yaml(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("::: not: valid: yaml: [", encoding="utf-8")
    assert load_pricing(bad).tiers == {}


def test_load_pricing_real_file_has_opus() -> None:
    # Smoke test against the committed config/model_pricing.yaml.
    table = load_pricing()
    assert table.resolve_tier("claude-opus-4-7") == "opus"


# --------------------------------------------------------------------------- #
# cost.py — pure
# --------------------------------------------------------------------------- #


def test_build_cost_report_aggregates_per_tier(pricing: PricingTable) -> None:
    rows = [
        ModelTokenRow("d1", "claude-opus-4-7", "opus", tokens_in=1_000_000),
        ModelTokenRow("d2", "claude-opus-4-7", "opus", tokens_out=1_000_000),
        ModelTokenRow("d3", "claude-sonnet-4-6", "sonnet", tokens_in=1_000_000),
    ]
    report = build_cost_report(rows, pricing)
    assert report.by_tier["opus"].tokens_in == 1_000_000
    assert report.by_tier["opus"].tokens_out == 1_000_000
    assert report.by_tier["opus"].cost_usd == pytest.approx(15.0 + 75.0)
    assert report.by_tier["sonnet"].cost_usd == pytest.approx(3.0)
    assert report.total_cost_usd == pytest.approx(15.0 + 75.0 + 3.0)


def test_coverage_is_token_weighted_and_unknown_not_zero_rated(pricing: PricingTable) -> None:
    rows = [
        ModelTokenRow("d1", "claude-opus-4-7", "opus", tokens_in=900_000),
        ModelTokenRow("d2", "mystery", UNKNOWN_TIER, tokens_in=100_000),
    ]
    report = build_cost_report(rows, pricing)
    # Coverage on TOKEN denominator: 900k / 1000k = 90%.
    assert report.coverage_pct == pytest.approx(90.0)
    assert report.total_tokens == 1_000_000
    assert report.known_tokens == 900_000
    # Unknown tier present in the report, with cost None (NOT zero).
    assert UNKNOWN_TIER in report.by_tier
    assert report.by_tier[UNKNOWN_TIER].cost_usd is None
    assert report.by_tier[UNKNOWN_TIER].total_tokens() == 100_000
    # Cost total excludes the unknown tier's tokens.
    assert report.total_cost_usd == pytest.approx(900_000 / 1_000_000 * 15.0)
    assert report.is_fully_covered is False


def test_empty_report_coverage_is_zero_not_hundred(pricing: PricingTable) -> None:
    report = build_cost_report([], pricing)
    assert report.coverage_pct == 0.0
    assert report.is_fully_covered is False
    assert report.total_cost_usd == 0.0


# --------------------------------------------------------------------------- #
# analyze_cost.py — integration (monkeypatched roots, tmp DB)
# --------------------------------------------------------------------------- #


def test_analyze_happy_path_writes_breakdown(env, pricing) -> None:
    _insert_discussion(env.db_path, "d1", "2026-06-01T09:00:00Z", "2026-06-01T11:00:00Z")
    _write_transcript(
        env.projects_root,
        env.project_root,
        [
            _msg_line("m1", "2026-06-01T10:00:00Z", "claude-opus-4-7", input_tokens=1000),
            _msg_line("m2", "2026-06-01T10:05:00Z", "claude-sonnet-4-6", output_tokens=500),
        ],
    )
    summary = ac.analyze_cost(db_path=env.db_path, project_root=env.project_root, pricing=pricing)
    assert summary["messages_attributed"] == 2
    conn = sqlite3.connect(str(env.db_path))
    try:
        rows = ac.load_cost_rows(conn)
    finally:
        conn.close()
    tiers = {r.tier for r in rows}
    assert tiers == {"opus", "sonnet"}


def test_analyze_unknown_model_marked_not_dropped(env, pricing) -> None:
    _insert_discussion(env.db_path, "d1", "2026-06-01T09:00:00Z", "2026-06-01T11:00:00Z")
    _write_transcript(
        env.projects_root,
        env.project_root,
        [
            _msg_line("m1", "2026-06-01T10:00:00Z", "claude-opus-4-7", input_tokens=900_000),
            _msg_line("m2", "2026-06-01T10:05:00Z", "some-other-llm", input_tokens=100_000),
            _msg_line("m3", "2026-06-01T10:06:00Z", None, input_tokens=10),
        ],
    )
    ac.analyze_cost(db_path=env.db_path, project_root=env.project_root, pricing=pricing)
    conn = sqlite3.connect(str(env.db_path))
    try:
        report = build_cost_report(ac.load_cost_rows(conn), pricing)
    finally:
        conn.close()
    assert UNKNOWN_TIER in report.by_tier
    assert report.by_tier[UNKNOWN_TIER].cost_usd is None
    # Coverage is token-weighted: 900_000 known / 1_000_010 total = 90.0%.
    assert report.coverage_pct == pytest.approx(90.0, abs=0.2)


def test_analyze_idempotent(env, pricing) -> None:
    _insert_discussion(env.db_path, "d1", "2026-06-01T09:00:00Z", "2026-06-01T11:00:00Z")
    _write_transcript(
        env.projects_root,
        env.project_root,
        [_msg_line("m1", "2026-06-01T10:00:00Z", "claude-opus-4-7", input_tokens=1000)],
    )
    ac.analyze_cost(
        db_path=env.db_path, project_root=env.project_root, full_rescan=True, pricing=pricing
    )
    ac.analyze_cost(
        db_path=env.db_path, project_root=env.project_root, full_rescan=True, pricing=pricing
    )
    conn = sqlite3.connect(str(env.db_path))
    try:
        count = conn.execute("SELECT COUNT(*) FROM discussion_model_tokens").fetchone()[0]
    finally:
        conn.close()
    assert count == 1


def test_watermark_skips_already_analyzed_closed_discussion(env, pricing) -> None:
    _insert_discussion(env.db_path, "d1", "2026-06-01T09:00:00Z", "2026-06-01T11:00:00Z")
    _write_transcript(
        env.projects_root,
        env.project_root,
        [_msg_line("m1", "2026-06-01T10:00:00Z", "claude-opus-4-7", input_tokens=1000)],
    )
    first = ac.analyze_cost(db_path=env.db_path, project_root=env.project_root, pricing=pricing)
    assert first["models_written"] == 1
    # Second incremental run: closed_at not newer than watermark -> nothing redone.
    second = ac.analyze_cost(db_path=env.db_path, project_root=env.project_root, pricing=pricing)
    assert second["models_written"] == 0


def test_target_selection_includes_unanalyzed_discussion_at_watermark(env) -> None:
    # Regression (review BLOCKING): two closed discussions share an exact
    # closed_at. d1 is already analyzed (has a breakdown row); d2 is new and
    # unanalyzed. A strict closed_at > watermark test would silently skip d2 —
    # the not-yet-analyzed backstop must still select it.
    _insert_discussion(env.db_path, "d1", "2026-06-01T09:00:00Z", "2026-06-01T11:00:00Z")
    _insert_discussion(env.db_path, "d2", "2026-06-01T09:00:00Z", "2026-06-01T11:00:00Z")
    conn = sqlite3.connect(str(env.db_path))
    try:
        conn.execute(
            """INSERT INTO discussion_model_tokens
               (discussion_id, model_id, tier, message_count, computed_at)
               VALUES ('d1', 'claude-opus-4-7', 'opus', 1, '2026-06-01T12:00:00Z')"""
        )
        conn.commit()
        analyzed = ac._analyzed_discussion_ids(conn)
        targets = ac._target_discussion_ids(
            conn,
            watermark="2026-06-01T11:00:00Z",
            full_rescan=False,
            discussion_filter=None,
            analyzed=analyzed,
        )
    finally:
        conn.close()
    assert "d2" in targets  # new + unanalyzed + same closed_at as watermark -> not skipped
    assert "d1" not in targets  # already analyzed + closed_at == watermark -> skipped


def test_full_rescan_reprocesses_despite_watermark(env, pricing) -> None:
    _insert_discussion(env.db_path, "d1", "2026-06-01T09:00:00Z", "2026-06-01T11:00:00Z")
    _write_transcript(
        env.projects_root,
        env.project_root,
        [_msg_line("m1", "2026-06-01T10:00:00Z", "claude-opus-4-7", input_tokens=1000)],
    )
    ac.analyze_cost(db_path=env.db_path, project_root=env.project_root, pricing=pricing)
    rescan = ac.analyze_cost(
        db_path=env.db_path, project_root=env.project_root, full_rescan=True, pricing=pricing
    )
    assert rescan["models_written"] == 1


def test_dry_run_writes_nothing(env, pricing) -> None:
    _insert_discussion(env.db_path, "d1", "2026-06-01T09:00:00Z", "2026-06-01T11:00:00Z")
    _write_transcript(
        env.projects_root,
        env.project_root,
        [_msg_line("m1", "2026-06-01T10:00:00Z", "claude-opus-4-7", input_tokens=1000)],
    )
    ac.analyze_cost(
        db_path=env.db_path, project_root=env.project_root, dry_run=True, pricing=pricing
    )
    conn = sqlite3.connect(str(env.db_path))
    try:
        count = conn.execute("SELECT COUNT(*) FROM discussion_model_tokens").fetchone()[0]
    finally:
        conn.close()
    assert count == 0


def test_corrupt_jsonl_line_skipped(env, pricing) -> None:
    _insert_discussion(env.db_path, "d1", "2026-06-01T09:00:00Z", "2026-06-01T11:00:00Z")
    _write_transcript(
        env.projects_root,
        env.project_root,
        [
            "{ this is not valid json",
            _msg_line("m1", "2026-06-01T10:00:00Z", "claude-opus-4-7", input_tokens=1000),
            "",
        ],
    )
    summary = ac.analyze_cost(db_path=env.db_path, project_root=env.project_root, pricing=pricing)
    assert summary["messages_attributed"] == 1


def test_sql_injection_shaped_model_id_is_inert(env, pricing) -> None:
    _insert_discussion(env.db_path, "d1", "2026-06-01T09:00:00Z", "2026-06-01T11:00:00Z")
    evil = "'; DROP TABLE discussion_model_tokens; --"
    _write_transcript(
        env.projects_root,
        env.project_root,
        [_msg_line("m1", "2026-06-01T10:00:00Z", evil, input_tokens=10)],
    )
    ac.analyze_cost(db_path=env.db_path, project_root=env.project_root, pricing=pricing)
    conn = sqlite3.connect(str(env.db_path))
    try:
        # Table still exists and stored the literal model id.
        stored = conn.execute(
            "SELECT model_id FROM discussion_model_tokens WHERE discussion_id='d1'"
        ).fetchone()
    finally:
        conn.close()
    assert stored[0] == evil


def test_sparse_discussion_with_no_messages(env, pricing) -> None:
    # Discussion exists but its window contains no transcript messages.
    _insert_discussion(env.db_path, "d1", "2026-06-01T09:00:00Z", "2026-06-01T11:00:00Z")
    _write_transcript(
        env.projects_root,
        env.project_root,
        [_msg_line("m1", "2020-01-01T00:00:00Z", "claude-opus-4-7", input_tokens=10)],
    )
    summary = ac.analyze_cost(db_path=env.db_path, project_root=env.project_root, pricing=pricing)
    assert summary["messages_attributed"] == 0


def test_missing_db_returns_empty_summary(tmp_path, monkeypatch, pricing) -> None:
    projects_root = tmp_path / "cp"
    projects_root.mkdir()
    project_root = tmp_path / "proj"
    project_root.mkdir()
    monkeypatch.setattr(itu, "CLAUDE_PROJECTS_ROOT", projects_root)
    monkeypatch.setattr(itu, "PROJECT_ROOT", project_root)
    _write_transcript(
        projects_root,
        project_root,
        [_msg_line("m1", "2026-06-01T10:00:00Z", "claude-opus-4-7", input_tokens=10)],
    )
    summary = ac.analyze_cost(
        db_path=tmp_path / "absent.db", project_root=project_root, pricing=pricing
    )
    assert summary == ac._empty_summary()


def test_no_transcripts_returns_empty_summary(env, pricing) -> None:
    # DB exists but no session transcript was written for this project.
    summary = ac.analyze_cost(db_path=env.db_path, project_root=env.project_root, pricing=pricing)
    assert summary["messages_seen"] == 0


# --------------------------------------------------------------------------- #
# Schema migration (new tables via shared init_db)
# --------------------------------------------------------------------------- #


def _columns(db_path: Path, table: str) -> set[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    finally:
        conn.close()


def test_fresh_db_has_telemetry_tables(tmp_path) -> None:
    db_path = _make_db(tmp_path)
    assert "tier" in _columns(db_path, "discussion_model_tokens")
    assert {"cache_read_tokens", "cache_create_tokens"} <= _columns(
        db_path, "discussion_model_tokens"
    )
    assert "value" in _columns(db_path, "telemetry_run_state")


def test_existing_db_without_table_gets_it(tmp_path) -> None:
    # Simulate a pre-telemetry DB: a real schema with the new tables dropped.
    db_path = _make_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("DROP TABLE discussion_model_tokens")
    conn.execute("DROP TABLE telemetry_run_state")
    conn.commit()
    conn.close()
    assert "discussion_model_tokens" not in _all_tables(db_path)
    init_db(db_path)  # re-init adds the missing tables (CREATE IF NOT EXISTS)
    assert "discussion_model_tokens" in _all_tables(db_path)
    assert "telemetry_run_state" in _all_tables(db_path)


def test_existing_db_with_table_is_idempotent(tmp_path) -> None:
    db_path = _make_db(tmp_path)
    before = _columns(db_path, "discussion_model_tokens")
    init_db(db_path)  # run again
    assert _columns(db_path, "discussion_model_tokens") == before


def _all_tables(db_path: Path) -> set[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        return {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    finally:
        conn.close()


# =========================================================================== #
# Layer A2 — failure signals (orphaned subagents + retry loops)
# =========================================================================== #


def _call(
    name: str, input_hash: str, message_id: str, *, tier: str = "opus", out: int = 0
) -> ToolCall:
    return ToolCall(
        name=name, input_hash=input_hash, message_id=message_id, tier=tier, tokens_out=out
    )


# --- detect_retry_loops (pure) --------------------------------------------- #


def test_retry_loop_flags_three_identical_in_a_row() -> None:
    calls = [
        _call("Bash", "h1", "m1", out=10),
        _call("Bash", "h1", "m2", out=10),
        _call("Bash", "h1", "m3", out=10),
    ]
    sigs = detect_retry_loops(calls)
    assert len(sigs) == 1
    assert sigs[0].failure_type == "retry_loop"
    assert sigs[0].occurrence_count == 3
    # Wasted = the redundant repeats (m2, m3) only — the first call is real work.
    assert sigs[0].wasted_tokens_out == 20


def test_retry_loop_below_threshold_not_flagged() -> None:
    calls = [_call("Bash", "h1", "m1"), _call("Bash", "h1", "m2")]
    assert detect_retry_loops(calls) == []


def test_retry_loop_threshold_clamped_to_two() -> None:
    # A threshold below 2 is meaningless (every call would "loop"); it clamps to 2.
    calls = [_call("Bash", "h1", "m1", out=10), _call("Bash", "h1", "m2", out=10)]
    sigs = detect_retry_loops(calls, threshold=1)
    assert len(sigs) == 1
    assert sigs[0].occurrence_count == 2


def test_retry_loop_distinct_inputs_not_a_loop() -> None:
    calls = [_call("Bash", "h1", "m1"), _call("Bash", "h2", "m2"), _call("Bash", "h3", "m3")]
    assert detect_retry_loops(calls) == []


def test_retry_loop_dedups_wasted_tokens_by_message_id() -> None:
    # One assistant message emitting three identical calls: occurrence_count is 3
    # but the wasted-token sum counts that message's usage once (m1 deduped).
    calls = [_call("Bash", "h1", "m1", out=10) for _ in range(3)]
    sigs = detect_retry_loops(calls)
    assert sigs[0].occurrence_count == 3
    assert sigs[0].wasted_tokens_out == 10


def test_retry_loop_detects_two_separate_loops() -> None:
    calls = [
        _call("A", "h1", "m1"),
        _call("A", "h1", "m2"),
        _call("A", "h1", "m3"),
        _call("B", "h2", "m4"),
        _call("B", "h2", "m5"),
        _call("B", "h2", "m6"),
    ]
    sigs = detect_retry_loops(calls)
    assert len(sigs) == 2
    assert {s.signature for s in sigs} == {"A:h1", "B:h2"}


def test_retry_loop_interleaved_calls_not_flagged() -> None:
    # Ping-pong A,B,A,B,A repeats A 3x but never in an unbroken run — by design
    # only consecutive runs are flagged (conservative; documented A2.1 gap).
    calls = [
        _call("A", "h1", "m1"),
        _call("B", "h2", "m2"),
        _call("A", "h1", "m3"),
        _call("B", "h2", "m4"),
        _call("A", "h1", "m5"),
    ]
    assert detect_retry_loops(calls) == []


def test_retry_loop_empty_input_returns_empty() -> None:
    assert detect_retry_loops([]) == []


# --- detect_orphaned_subagents (pure) -------------------------------------- #


def test_orphan_dispatch_without_result_is_flagged() -> None:
    sigs = detect_orphaned_subagents([SubagentDispatch("toolu_1", "qa-specialist")], set(), [])
    assert len(sigs) == 1
    assert sigs[0].failure_type == "orphaned_subagent"
    assert sigs[0].signature == "toolu_1"


def test_orphan_dispatch_with_result_not_flagged() -> None:
    sigs = detect_orphaned_subagents([SubagentDispatch("toolu_1", "qa")], {"toolu_1"}, [])
    assert sigs == []


def test_orphan_background_dispatch_without_result_not_flagged() -> None:
    # run_in_background dispatches return async — a missing sync result is normal.
    d = [SubagentDispatch("toolu_1", "qa", run_in_background=True)]
    assert detect_orphaned_subagents(d, set(), []) == []


def test_orphan_incomplete_run_flagged() -> None:
    runs = [SubagentRun("aX", None, completed=False, tier="opus", tokens_out=100)]
    sigs = detect_orphaned_subagents([], set(), runs)
    assert len(sigs) == 1
    assert sigs[0].signature == "aX"
    assert sigs[0].wasted_tokens_out == 100


def test_orphan_completed_run_not_flagged() -> None:
    runs = [SubagentRun("aX", None, completed=True, tier="opus")]
    assert detect_orphaned_subagents([], set(), runs) == []


def test_orphan_linked_run_not_double_counted() -> None:
    # A dispatch with no result whose subagent run is linked by source id must be
    # reported once (the dispatch), with the run's tokens pulled in for weighting.
    d = [SubagentDispatch("toolu_1", "qa")]
    runs = [SubagentRun("aX", "toolu_1", completed=False, tier="opus", tokens_out=50)]
    sigs = detect_orphaned_subagents(d, set(), runs)
    assert len(sigs) == 1
    assert sigs[0].signature == "toolu_1"
    assert sigs[0].wasted_tokens_out == 50


# --- rank_failures (pure) -------------------------------------------------- #


def test_rank_priced_before_unpriced(pricing: PricingTable) -> None:
    s_unknown = FailureSignal("retry_loop", "u", 1, UNKNOWN_TIER, wasted_tokens_out=100000)
    s_opus = FailureSignal("retry_loop", "o", 1, "opus", wasted_tokens_out=10)
    ranked = rank_failures([s_unknown, s_opus], pricing)
    # Priced opus ranks first despite far fewer tokens; unknown is uncosted (None).
    assert ranked[0].signal.tier == "opus"
    assert ranked[0].cost_usd is not None
    assert ranked[1].cost_usd is None


def test_rank_unpriced_ordered_by_wasted_tokens(pricing: PricingTable) -> None:
    a = FailureSignal("retry_loop", "a", 1, UNKNOWN_TIER, wasted_tokens_out=100)
    b = FailureSignal("retry_loop", "b", 1, UNKNOWN_TIER, wasted_tokens_out=500)
    ranked = rank_failures([a, b], pricing)
    assert ranked[0].signal.signature == "b"


def test_wasted_total_tokens_treats_none_as_zero() -> None:
    s = FailureSignal(
        "retry_loop",
        "x",
        1,
        "opus",
        wasted_tokens_in=None,
        wasted_tokens_out=5,
        wasted_cache_read_tokens=None,
        wasted_cache_create_tokens=2,
    )
    assert s.wasted_total_tokens() == 7


# --- transport helpers ----------------------------------------------------- #


def _assistant_line(
    mid: str,
    ts: str,
    model: str,
    tool_uses: list[tuple[str, str, dict]],
    *,
    stop_reason: str = "end_turn",
    output_tokens: int = 0,
    cache_read: int = 0,
) -> str:
    content = [
        {"type": "tool_use", "id": tid, "name": name, "input": inp} for tid, name, inp in tool_uses
    ]
    msg = {
        "role": "assistant",
        "id": mid,
        "model": model,
        "stop_reason": stop_reason,
        "usage": {
            "input_tokens": 0,
            "output_tokens": output_tokens,
            "cache_read_input_tokens": cache_read,
            "cache_creation_input_tokens": 0,
        },
        "content": content,
    }
    return json.dumps({"timestamp": ts, "message": msg})


def _result_line(ts: str, tool_use_id: str) -> str:
    return json.dumps(
        {
            "timestamp": ts,
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": tool_use_id}],
            },
        }
    )


def _subagent_line(
    mid: str, ts: str, model: str, *, stop_reason: str = "end_turn", output_tokens: int = 0
) -> str:
    msg = {
        "role": "assistant",
        "id": mid,
        "model": model,
        "stop_reason": stop_reason,
        "usage": {
            "input_tokens": 0,
            "output_tokens": output_tokens,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
        "content": [{"type": "text", "text": "ok"}],
    }
    return json.dumps({"timestamp": ts, "message": msg})


def _write_session(
    projects_root: Path,
    project_root: Path,
    sid: str,
    main_lines: list[str],
    subagents: dict[str, list[str]] | None = None,
) -> Path:
    """Create a <slug>/<sid>/ session dir with main + subagent transcripts.

    Returns the session directory path (so tests can set mtimes deterministically).
    """
    slug = itu._project_slug(project_root)
    sdir = projects_root / slug / sid
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / f"{sid}.jsonl").write_text("\n".join(main_lines), encoding="utf-8")
    if subagents:
        sub = sdir / "subagents"
        sub.mkdir(exist_ok=True)
        for name, lines in subagents.items():
            (sub / f"agent-{name}.jsonl").write_text("\n".join(lines), encoding="utf-8")
    return sdir


def _set_mtime(session_dir: Path, mtime: float) -> None:
    for path in session_dir.rglob("*.jsonl"):
        os.utime(path, (mtime, mtime))


# --- transport: parsing ---------------------------------------------------- #


def test_input_hash_is_order_independent_and_value_sensitive() -> None:
    assert af._input_hash({"a": 1, "b": 2}) == af._input_hash({"b": 2, "a": 1})
    assert af._input_hash({"a": 1}) != af._input_hash({"a": 2})


def test_parse_main_session_extracts_calls_dispatch_and_results(
    tmp_path: Path, pricing: PricingTable
) -> None:
    lines = [
        _assistant_line(
            "m1",
            "2026-01-01T00:00:01Z",
            "claude-opus-4-7",
            [("toolu_a", "Bash", {"c": "ls"})],
            output_tokens=5,
        ),
        _result_line("2026-01-01T00:00:02Z", "toolu_a"),
        _assistant_line(
            "m2",
            "2026-01-01T00:00:03Z",
            "claude-opus-4-7",
            [("toolu_b", "Agent", {"subagent_type": "qa"})],
        ),
    ]
    path = tmp_path / "s.jsonl"
    path.write_text("\n".join(lines), encoding="utf-8")
    calls, dispatches, results = af.parse_main_session(path, pricing)
    assert [c.name for c in calls] == ["Bash", "Agent"]
    assert calls[0].tier == "opus"
    assert len(dispatches) == 1 and dispatches[0].subagent_type == "qa"
    assert results == {"toolu_a"}


def test_parse_subagent_run_completed_vs_incomplete(tmp_path: Path, pricing: PricingTable) -> None:
    done = tmp_path / "agent-done.jsonl"
    done.write_text(
        _subagent_line("s1", "2026-01-01T00:00:01Z", "claude-opus-4-7", output_tokens=20),
        encoding="utf-8",
    )
    hung = tmp_path / "agent-hung.jsonl"
    hung.write_text(
        _subagent_line(
            "s2",
            "2026-01-01T00:00:01Z",
            "claude-opus-4-7",
            stop_reason="tool_use",
            output_tokens=99,
        ),
        encoding="utf-8",
    )
    run_done = af.parse_subagent_run(done, pricing)
    run_hung = af.parse_subagent_run(hung, pricing)
    assert run_done.completed is True and run_done.agent_id == "done"
    assert run_hung.completed is False and run_hung.tokens_out == 99


# --- transport: end-to-end ------------------------------------------------- #


def test_analyze_failures_detects_orphan_and_retry(env, pricing: PricingTable) -> None:
    main = [
        _assistant_line(
            "m1",
            "2026-01-01T00:00:01Z",
            "claude-opus-4-7",
            [("t1", "Bash", {"c": "ls"})],
            output_tokens=10,
        ),
        _result_line("2026-01-01T00:00:02Z", "t1"),
        _assistant_line(
            "m2",
            "2026-01-01T00:00:03Z",
            "claude-opus-4-7",
            [("t2", "Bash", {"c": "ls"})],
            output_tokens=10,
        ),
        _result_line("2026-01-01T00:00:04Z", "t2"),
        _assistant_line(
            "m3",
            "2026-01-01T00:00:05Z",
            "claude-opus-4-7",
            [("t3", "Bash", {"c": "ls"})],
            output_tokens=10,
        ),
        _result_line("2026-01-01T00:00:06Z", "t3"),
        _assistant_line(
            "m4",
            "2026-01-01T00:00:07Z",
            "claude-opus-4-7",
            [("t4", "Agent", {"subagent_type": "qa"})],
        ),
    ]
    _write_session(env.projects_root, env.project_root, "sess1", main)
    summary = af.analyze_failures(db_path=env.db_path, full_rescan=True, pricing=pricing)
    assert summary["retry_loops"] == 1
    assert summary["orphaned_subagents"] == 1
    assert summary["rows_written"] == 2


def test_analyze_failures_flags_incomplete_subagent(env, pricing: PricingTable) -> None:
    main = [
        _assistant_line(
            "m1",
            "2026-01-01T00:00:01Z",
            "claude-opus-4-7",
            [("t1", "Agent", {"subagent_type": "qa"})],
        ),
        _result_line(
            "2026-01-01T00:00:02Z", "t1"
        ),  # dispatch HAS a result -> not a no-result orphan
    ]
    hung = [
        _subagent_line(
            "s1",
            "2026-01-01T00:00:03Z",
            "claude-opus-4-7",
            stop_reason="tool_use",
            output_tokens=100,
        )
    ]
    _write_session(env.projects_root, env.project_root, "sess2", main, {"hung": hung})
    summary = af.analyze_failures(db_path=env.db_path, full_rescan=True, pricing=pricing)
    assert summary["orphaned_subagents"] == 1


def test_analyze_failures_clean_session_reports_nothing(env, pricing: PricingTable) -> None:
    main = [
        _assistant_line(
            "m1",
            "2026-01-01T00:00:01Z",
            "claude-opus-4-7",
            [("t1", "Bash", {"c": "ls"})],
            output_tokens=5,
        ),
        _result_line("2026-01-01T00:00:02Z", "t1"),
        _assistant_line(
            "m2",
            "2026-01-01T00:00:03Z",
            "claude-opus-4-7",
            [("t2", "Read", {"p": "x"})],
            output_tokens=5,
        ),
        _result_line("2026-01-01T00:00:04Z", "t2"),
    ]
    _write_session(env.projects_root, env.project_root, "clean", main)
    summary = af.analyze_failures(db_path=env.db_path, full_rescan=True, pricing=pricing)
    assert summary["retry_loops"] == 0
    assert summary["orphaned_subagents"] == 0
    assert summary["rows_written"] == 0


def test_analyze_failures_is_idempotent(env, pricing: PricingTable) -> None:
    main = [
        _assistant_line(
            "m1",
            "2026-01-01T00:00:01Z",
            "claude-opus-4-7",
            [("t1", "Agent", {"subagent_type": "qa"})],
        ),
    ]
    _write_session(env.projects_root, env.project_root, "s", main)
    af.analyze_failures(db_path=env.db_path, full_rescan=True, pricing=pricing)
    conn = sqlite3.connect(str(env.db_path))
    first = conn.execute("SELECT COUNT(*) FROM telemetry_failures").fetchone()[0]
    conn.close()
    af.analyze_failures(db_path=env.db_path, full_rescan=True, pricing=pricing)
    conn = sqlite3.connect(str(env.db_path))
    second = conn.execute("SELECT COUNT(*) FROM telemetry_failures").fetchone()[0]
    conn.close()
    assert first == second == 1


def test_failure_attributed_to_discussion_window(env, pricing: PricingTable) -> None:
    _insert_discussion(env.db_path, "DISC-x", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z")
    main = [
        _assistant_line(
            "m1",
            "2026-01-01T12:00:00Z",
            "claude-opus-4-7",
            [("t1", "Agent", {"subagent_type": "qa"})],
        ),
    ]
    _write_session(env.projects_root, env.project_root, "s", main)
    af.analyze_failures(db_path=env.db_path, full_rescan=True, pricing=pricing)
    conn = sqlite3.connect(str(env.db_path))
    row = conn.execute("SELECT discussion_id FROM telemetry_failures").fetchone()
    conn.close()
    assert row[0] == "DISC-x"


def test_failures_mtime_watermark_skips_older_sessions(env, pricing: PricingTable) -> None:
    older = _write_session(
        env.projects_root,
        env.project_root,
        "older",
        [
            _assistant_line(
                "m1",
                "2026-01-01T00:00:01Z",
                "claude-opus-4-7",
                [("t1", "Agent", {"subagent_type": "qa"})],
            )
        ],
    )
    newer = _write_session(
        env.projects_root,
        env.project_root,
        "newer",
        [
            _assistant_line(
                "m2",
                "2026-01-01T00:00:01Z",
                "claude-opus-4-7",
                [("t2", "Agent", {"subagent_type": "qa"})],
            )
        ],
    )
    _set_mtime(older, 1000.0)
    _set_mtime(newer, 2000.0)
    full = af.analyze_failures(db_path=env.db_path, full_rescan=True, pricing=pricing)
    assert full["sessions_analyzed"] == 2
    incr = af.analyze_failures(db_path=env.db_path, pricing=pricing)
    # Only the newer session (>= watermark) is re-analyzed; the older is skipped.
    assert incr["sessions_analyzed"] == 1


@pytest.mark.regression
def test_failures_watermark_boundary_not_silently_skipped(env, pricing: PricingTable) -> None:
    # Regression: a session whose mtime exactly equals the stored watermark must
    # STILL be re-analyzed (the selector uses >=, not >). A strict > would
    # silently skip it — the same same-timestamp hole the A1 review caught.
    s = _write_session(
        env.projects_root,
        env.project_root,
        "boundary",
        [
            _assistant_line(
                "m1",
                "2026-01-01T00:00:01Z",
                "claude-opus-4-7",
                [("t1", "Agent", {"subagent_type": "qa"})],
            )
        ],
    )
    _set_mtime(s, 5000.0)
    af.analyze_failures(
        db_path=env.db_path, full_rescan=True, pricing=pricing
    )  # watermark -> 5000
    incr = af.analyze_failures(db_path=env.db_path, pricing=pricing)
    assert incr["sessions_analyzed"] == 1  # boundary session not skipped


def test_telemetry_failures_table_exists(tmp_path: Path) -> None:
    db_path = _make_db(tmp_path)
    cols = _columns(db_path, "telemetry_failures")
    assert {"failure_type", "signature", "tier", "wasted_tokens_out", "occurrence_count"} <= cols


def test_parse_subagent_run_empty_transcript_is_incomplete(
    tmp_path: Path, pricing: PricingTable
) -> None:
    # An empty subagent transcript has produced no answer -> incomplete (orphan).
    empty = tmp_path / "agent-empty.jsonl"
    empty.write_text("", encoding="utf-8")
    run = af.parse_subagent_run(empty, pricing)
    assert run.completed is False
    assert run.tokens_out is None


def test_analyze_failures_dispatched_orphan_tier_is_unknown(env, pricing: PricingTable) -> None:
    # A no-result dispatch is detected parent-side; subagent files carry no
    # back-link, so its tier is honestly 'unknown' (never zero-rated) — documents
    # the dead-seam: the run-link path is unreachable from the transport.
    main = [
        _assistant_line(
            "m1",
            "2026-01-01T00:00:01Z",
            "claude-opus-4-7",
            [("t1", "Agent", {"subagent_type": "qa"})],
        ),
    ]
    _write_session(env.projects_root, env.project_root, "s", main)
    af.analyze_failures(db_path=env.db_path, full_rescan=True, pricing=pricing)
    conn = sqlite3.connect(str(env.db_path))
    row = conn.execute(
        "SELECT tier, wasted_tokens_out FROM telemetry_failures "
        "WHERE failure_type='orphaned_subagent'"
    ).fetchone()
    conn.close()
    assert row[0] == "unknown"
    assert row[1] is None


@pytest.mark.regression
def test_migration_allowlist_rejects_unsafe_identifier() -> None:
    # Regression (security B1): the ALTER TABLE migration loop interpolates DDL
    # identifiers (SQLite can't bind them). An off-allowlist table/column/type
    # must be rejected loudly so a future non-literal entry can't become injection.
    from scripts.init_db import _assert_safe_migration

    _assert_safe_migration("turns", "tokens_in", "INTEGER")  # known-good: no raise
    with pytest.raises(ValueError):
        _assert_safe_migration("turns; DROP TABLE turns", "x", "TEXT")
    with pytest.raises(ValueError):
        _assert_safe_migration("turns", "x) --", "TEXT")
    with pytest.raises(ValueError):
        _assert_safe_migration("turns", "x", "TEXT; DROP TABLE turns")


@pytest.mark.regression
def test_subagent_file_outside_projects_root_is_skipped(
    env, pricing: PricingTable, monkeypatch
) -> None:
    # Regression (security B2): _detect_for_session must consult
    # _is_inside_projects_root before opening subagent files (symlink-escape
    # guard). Before the fix the guard was absent here, so an escaping agent file
    # would be read and flagged. Forcing the guard to reject agent-* paths must
    # now suppress the orphan (old code would still report 1).
    main = [
        _assistant_line(
            "m1",
            "2026-01-01T00:00:01Z",
            "claude-opus-4-7",
            [("t1", "Agent", {"subagent_type": "qa"})],
        ),
        _result_line("2026-01-01T00:00:02Z", "t1"),
    ]
    hung = [
        _subagent_line(
            "s1",
            "2026-01-01T00:00:03Z",
            "claude-opus-4-7",
            stop_reason="tool_use",
            output_tokens=10,
        )
    ]
    _write_session(env.projects_root, env.project_root, "s", main, {"hung": hung})
    real = itu._is_inside_projects_root
    monkeypatch.setattr(
        itu, "_is_inside_projects_root", lambda p: False if "agent-" in str(p) else real(p)
    )
    summary = af.analyze_failures(db_path=env.db_path, full_rescan=True, pricing=pricing)
    assert summary["orphaned_subagents"] == 0
