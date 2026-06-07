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
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scripts import ingest_token_usage as itu
from scripts.init_db import init_db
from scripts.telemetry import analyze_cost as ac
from scripts.telemetry import analyze_failures as af
from scripts.telemetry import analyze_value as av
from scripts.telemetry import dashboard as dash
from src.telemetry.cost import CostReport, ModelTokenRow, build_cost_report
from src.telemetry.dashboard import (
    STATE_DATA,
    STATE_NOT_RUN,
    DashboardData,
    render_console_summary,
    render_dashboard_html,
)
from src.telemetry.failures import (
    FailureSignal,
    RankedFailure,
    SubagentDispatch,
    SubagentRun,
    ToolCall,
    detect_orphaned_subagents,
    detect_retry_loops,
    rank_failures,
)
from src.telemetry.live import (
    LANE_ACTIVE,
    LANE_COMPLETE,
    LANE_ORPHANED,
    RECENT_EVENTS_CAP,
    RUNWAY_AMBER,
    RUNWAY_AMBER_DEFAULT,
    RUNWAY_OK,
    RUNWAY_RED,
    RUNWAY_RED_DEFAULT,
    LiveEvent,
    apply_event,
    empty_state,
    fold_events,
    mark_orphans,
)
from src.telemetry.pricing import (
    UNKNOWN_TIER,
    PricingTable,
    load_pricing,
    parse_pricing,
)
from src.telemetry.value import (
    FLAW_ATTRIBUTION,
    FLAW_PRICING,
    DivergenceResult,
    IndependentEstimate,
    LeverageResult,
    SubscriptionFee,
    cross_check,
    leverage,
    load_subscription_fee,
    parse_subscription_fee,
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
    # is_inside_projects_root before opening subagent files (symlink-escape
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
    real = itu.is_inside_projects_root
    monkeypatch.setattr(
        itu, "is_inside_projects_root", lambda p: False if "agent-" in str(p) else real(p)
    )
    summary = af.analyze_failures(db_path=env.db_path, full_rescan=True, pricing=pricing)
    assert summary["orphaned_subagents"] == 0


@pytest.mark.regression
def test_ingest_migration_allowlist_rejects_unsafe_identifier() -> None:
    # Regression (security B1 mirror): the ALTER TABLE loop in
    # ingest_token_usage._ensure_token_columns interpolates DDL identifiers
    # (SQLite can't bind them). Its own _assert_safe_migration guard must reject
    # off-allowlist table/column/type so a future non-literal entry can't inject.
    itu._assert_safe_migration("turns", "tokens_in", "INTEGER")  # known-good: no raise
    with pytest.raises(ValueError):
        itu._assert_safe_migration("turns; DROP TABLE turns", "x", "INTEGER")
    with pytest.raises(ValueError):
        itu._assert_safe_migration("turns", "x) --", "INTEGER")
    with pytest.raises(ValueError):
        itu._assert_safe_migration("turns", "x", "TEXT; DROP TABLE turns")
    # ingest's allowlist is intentionally narrower than init_db's — it only ever
    # adds INTEGER token columns, so even a plain TEXT must be rejected here.
    with pytest.raises(ValueError):
        itu._assert_safe_migration("turns", "x", "TEXT")


def test_ingest_migration_allowlist_is_subset_of_init_db() -> None:
    # Drift guard (arch advisory): the two _assert_safe_migration allowlists are
    # intentionally duplicated and ingest's is the narrower one. Enforce the
    # subset invariant so a future edit can't let ingest allow a table/type that
    # init_db's guard would reject — turning the "keep in sync" comment into a
    # tested contract without coupling the two modules at runtime.
    from scripts import init_db as idb

    assert itu._MIGRATION_ALLOWED_TABLES <= idb._MIGRATION_ALLOWED_TABLES
    assert itu._MIGRATION_ALLOWED_TYPES <= idb._MIGRATION_ALLOWED_TYPES


def test_init_db_quiet_suppresses_print(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    # quiet=True is a behavioral contract (the analyzers rely on it to keep their
    # stdout clean), so assert the suppression directly, not just as a side effect.
    db_path = tmp_path / "evaluation.db"
    init_db(db_path, quiet=False)
    assert "Database initialized" in capsys.readouterr().out
    init_db(db_path, quiet=True)  # re-init is idempotent (CREATE IF NOT EXISTS)
    assert capsys.readouterr().out == ""


def test_session_mtime_returns_newest_and_handles_scandir_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # _session_mtime computes the incremental watermark; verify it returns the
    # newest subagent mtime and degrades to 0.0 if the directory scan fails.
    monkeypatch.setattr(itu, "is_inside_projects_root", lambda p: True)
    sub = tmp_path / "subagents"
    sub.mkdir()
    (sub / "agent-a.jsonl").write_text("{}", encoding="utf-8")
    (sub / "agent-b.jsonl").write_text("{}", encoding="utf-8")
    os.utime(sub / "agent-a.jsonl", (1000.0, 1000.0))
    os.utime(sub / "agent-b.jsonl", (2000.0, 2000.0))
    group: dict[str, object] = {"subagents": sub}
    assert af._session_mtime(group) == 2000.0

    def _boom(_path: object) -> None:
        raise OSError("scandir failed")

    monkeypatch.setattr(af.os, "scandir", _boom)
    assert af._session_mtime(group) == 0.0


@pytest.mark.regression
def test_session_mtime_skips_entry_outside_projects_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Regression (security advisory): _session_mtime must consult
    # is_inside_projects_root before stat'ing each subagent entry, matching the
    # symlink-escape guard _detect_for_session applies before opening files.
    # Rejecting the only entry must yield 0.0 (excluded, never stat'd).
    sub = tmp_path / "subagents"
    sub.mkdir()
    (sub / "agent-escape.jsonl").write_text("{}", encoding="utf-8")
    os.utime(sub / "agent-escape.jsonl", (1500.0, 1500.0))
    monkeypatch.setattr(itu, "is_inside_projects_root", lambda p: False)
    assert af._session_mtime({"subagents": sub}) == 0.0


# --------------------------------------------------------------------------- #
# value.py (A3) — pure leverage + cross-check
# --------------------------------------------------------------------------- #


def _report(total_cost: float, total_tokens: int = 1000, known: int | None = None) -> CostReport:
    """A minimal CostReport for pure A3 tests (coverage = known/total)."""
    known = total_tokens if known is None else known
    return CostReport(
        by_tier={}, total_cost_usd=total_cost, known_tokens=known, total_tokens=total_tokens
    )


def _table_row_counts(db_path: Path) -> dict[str, int]:
    """Snapshot every table's row count — used to prove A3 persists nothing."""
    conn = sqlite3.connect(str(db_path))
    try:
        names = [
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        ]
        return {n: conn.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in names}
    finally:
        conn.close()


def test_leverage_not_configured() -> None:
    res = leverage(_report(666.0), None)
    assert res.configured is False
    assert res.leverage_cumulative is None
    assert "not configured" in res.reason


def test_leverage_configured_with_window() -> None:
    res = leverage(_report(100.0), SubscriptionFee(monthly_fee_usd=20.0), window_months=2.0)
    assert res.configured is True
    assert res.leverage_cumulative == pytest.approx(5.0)  # 100 / 20
    assert res.leverage_per_month == pytest.approx(2.5)  # (100/2) / 20
    assert res.note == "" and res.reason == ""


def test_leverage_configured_no_window_sets_note_not_reason() -> None:
    res = leverage(_report(100.0), SubscriptionFee(monthly_fee_usd=20.0))
    assert res.configured is True
    assert res.leverage_per_month is None
    assert res.reason == ""  # reason is reserved for the not-configured case
    assert res.note  # the per-month advisory lives here


def test_leverage_nonfinite_total_is_honest_absence() -> None:
    res = leverage(_report(float("inf")), SubscriptionFee(monthly_fee_usd=20.0))
    assert res.configured is False
    assert "finite" in res.reason


def test_leverage_epsilon_fee_does_not_crash() -> None:
    import math

    res = leverage(_report(100.0), SubscriptionFee(monthly_fee_usd=1e-9), window_months=1.0)
    assert res.configured is True
    assert math.isfinite(res.leverage_cumulative)


@pytest.mark.parametrize("raw", [0, 0.0, -5, "free", None, True])
def test_parse_subscription_fee_invalid_is_none(raw) -> None:
    assert parse_subscription_fee({"monthly_fee_usd": raw}) is None


def test_parse_subscription_fee_valid() -> None:
    fee = parse_subscription_fee(
        {"monthly_fee_usd": 20, "currency": "USD", "plan_label": "Max", "effective_date": "2026"}
    )
    assert fee is not None
    assert fee.monthly_fee_usd == 20.0
    assert fee.plan_label == "Max"


def test_parse_subscription_fee_non_dict_is_none() -> None:
    assert parse_subscription_fee([1, 2]) is None


def test_load_subscription_fee_missing_file_is_none(tmp_path: Path) -> None:
    assert load_subscription_fee(tmp_path / "nope.yaml") is None


def test_load_subscription_fee_bad_yaml_is_none(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text("::: not : yaml :::", encoding="utf-8")
    assert load_subscription_fee(p) is None


def test_load_subscription_fee_valid(tmp_path: Path) -> None:
    p = tmp_path / "sub.yaml"
    p.write_text("monthly_fee_usd: 30.0\nplan_label: Pro\n", encoding="utf-8")
    fee = load_subscription_fee(p)
    assert fee is not None and fee.monthly_fee_usd == 30.0


def test_cross_check_absent_none_is_typed() -> None:
    res = cross_check(_report(666.0), None)
    assert res.available is False
    assert res.divergence_pct is None
    assert "no independent estimate" in res.reason


def test_cross_check_not_present_is_absent() -> None:
    ind = IndependentEstimate(
        present=False,
        cost_usd=None,
        token_basis=0,
        source_label="otel",
        scope_coverage_pct=0.0,
        flaw_class=FLAW_PRICING,
    )
    assert cross_check(_report(666.0), ind).available is False


def test_cross_check_uncosted_is_absent() -> None:
    ind = IndependentEstimate(
        present=True,
        cost_usd=None,
        token_basis=5,
        source_label="otel",
        scope_coverage_pct=10.0,
        flaw_class=FLAW_PRICING,
    )
    res = cross_check(_report(666.0), ind)
    assert res.available is False
    assert "could not be costed" in res.reason


def test_cross_check_zero_denominator_is_absent_not_zero() -> None:
    ind = IndependentEstimate(
        present=True,
        cost_usd=0.0,
        token_basis=0,
        source_label="base",
        scope_coverage_pct=0.0,
        flaw_class=FLAW_ATTRIBUTION,
    )
    res = cross_check(_report(666.0), ind)
    assert res.available is False  # never available=True with a None divergence
    assert res.divergence_pct is None  # and never a misleading 0.0
    assert res.independent_cost_usd == 0.0  # the source is still surfaced


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0])
def test_cross_check_unusable_independent_is_absent(bad) -> None:
    ind = IndependentEstimate(
        present=True,
        cost_usd=bad,
        token_basis=1,
        source_label="base",
        scope_coverage_pct=1.0,
        flaw_class=FLAW_ATTRIBUTION,
    )
    res = cross_check(_report(666.0), ind)
    assert res.available is False
    assert res.divergence_pct is None  # never a misleading 0.0 for "no data"


def test_leverage_zero_window_sets_note_not_reason() -> None:
    # window_months == 0 must yield configured=True with per-month absent (note,
    # not reason) — the contract boundary the None-window test does not cover.
    res = leverage(_report(100.0), SubscriptionFee(monthly_fee_usd=20.0), window_months=0.0)
    assert res.configured is True
    assert res.leverage_per_month is None
    assert res.reason == ""
    assert res.note


def test_cross_check_nonfinite_our_cost_is_absent() -> None:
    ind = IndependentEstimate(
        present=True,
        cost_usd=10.0,
        token_basis=1,
        source_label="base",
        scope_coverage_pct=100.0,
        flaw_class=FLAW_ATTRIBUTION,
    )
    assert cross_check(_report(float("nan")), ind).available is False


def test_cross_check_identical_is_zero_not_absent() -> None:
    ind = IndependentEstimate(
        present=True,
        cost_usd=666.0,
        token_basis=10,
        source_label="base",
        scope_coverage_pct=100.0,
        flaw_class=FLAW_PRICING,
    )
    res = cross_check(_report(666.0), ind)
    assert res.available is True
    assert res.divergence_pct == 0.0
    assert res.direction is None  # exact match


def test_cross_check_ours_higher() -> None:
    ind = IndependentEstimate(
        present=True,
        cost_usd=500.0,
        token_basis=10,
        source_label="base",
        scope_coverage_pct=100.0,
        flaw_class=FLAW_PRICING,
    )
    res = cross_check(_report(666.0), ind)
    assert res.direction == "ours_higher"
    assert res.divergence_pct == pytest.approx(33.2)  # (666-500)/500*100
    assert res.flaw_class == "pricing"


def test_cross_check_ours_lower_attribution() -> None:
    ind = IndependentEstimate(
        present=True,
        cost_usd=2244.53,
        token_basis=10,
        source_label="base",
        scope_coverage_pct=100.0,
        flaw_class=FLAW_ATTRIBUTION,
    )
    res = cross_check(_report(666.26), ind)
    assert res.direction == "ours_lower"
    assert res.divergence_pct < 0
    assert res.flaw_class == "attribution"


def test_telemetry_package_exports_importable() -> None:
    # Circular-import guard at collection time: A1's cost.py is an A3 dependency,
    # so a circular import would only surface on package-root import.
    import src.telemetry as t

    for name in (
        "leverage",
        "cross_check",
        "load_subscription_fee",
        "LeverageResult",
        "DivergenceResult",
        "IndependentEstimate",
        "SubscriptionFee",
    ):
        assert hasattr(t, name)


# --------------------------------------------------------------------------- #
# analyze_value.py (A3) — transport: window, OTel ingest, integration
# --------------------------------------------------------------------------- #


def _msg_record(ts, *, model: str = "claude-opus-4-7", tokens: int = 1) -> itu.MessageRecord:
    return itu.MessageRecord(
        message_id="x",
        timestamp=ts,
        model=model,
        input_tokens=tokens,
        output_tokens=0,
        cache_read_tokens=0,
        cache_create_tokens=0,
        source_file=Path("x"),
    )


def test_window_months_spans_two_timestamps() -> None:
    from datetime import UTC, datetime

    msgs = {
        "a": _msg_record(datetime(2026, 1, 1, tzinfo=UTC)),
        "b": _msg_record(datetime(2026, 2, 1, tzinfo=UTC)),
    }
    months = av._window_months(msgs)
    assert months is not None
    assert 0.9 < months < 1.2  # ~31 days / 30.44


def test_window_months_too_few_is_none() -> None:
    from datetime import UTC, datetime

    assert av._window_months({}) is None
    assert av._window_months({"a": _msg_record(datetime(2026, 1, 1, tzinfo=UTC))}) is None


def _otel_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(av, "DATA_DIR", data_dir)
    return data_dir


def test_otel_estimate_present(tmp_path, monkeypatch) -> None:
    data_dir = _otel_env(tmp_path, monkeypatch)
    f = data_dir / "otel_export.jsonl"
    f.write_text(
        "\n".join(
            [
                json.dumps({"metric": "claude_code.cost.usage", "value": 1.5}),
                json.dumps({"metric": "claude_code.cost.usage", "value": 2.0}),
                json.dumps(
                    {
                        "metric": "claude_code.token.usage",
                        "value": 1000,
                        "attributes": {"type": "input"},
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    est = av._otel_estimate(f)
    assert est.present is True
    assert est.cost_usd == pytest.approx(3.5)
    assert est.token_basis == 1000
    assert est.flaw_class == "pricing"


def test_otel_estimate_missing_file_is_absent(tmp_path, monkeypatch) -> None:
    data_dir = _otel_env(tmp_path, monkeypatch)
    assert av._otel_estimate(data_dir / "otel_export.jsonl").present is False


def test_otel_estimate_rejects_path_outside_data_dir(tmp_path, monkeypatch) -> None:
    _otel_env(tmp_path, monkeypatch)
    outside = tmp_path / "outside.jsonl"  # exists, but not inside data/
    outside.write_text(
        json.dumps({"metric": "claude_code.cost.usage", "value": 9.9}), encoding="utf-8"
    )
    assert av._otel_estimate(outside).present is False


def test_otel_estimate_size_cap(tmp_path, monkeypatch) -> None:
    data_dir = _otel_env(tmp_path, monkeypatch)
    monkeypatch.setattr(av, "OTEL_MAX_BYTES", 5)
    f = data_dir / "otel_export.jsonl"
    f.write_text(json.dumps({"metric": "claude_code.cost.usage", "value": 1.0}), encoding="utf-8")
    assert av._otel_estimate(f).present is False


def test_otel_estimate_tolerant_of_bad_lines(tmp_path, monkeypatch) -> None:
    data_dir = _otel_env(tmp_path, monkeypatch)
    f = data_dir / "otel_export.jsonl"
    f.write_text(
        "\n".join(
            [
                "not json",
                "{bad",
                json.dumps({"metric": "claude_code.cost.usage", "value": 4.0}),
                "[]",
            ]
        ),
        encoding="utf-8",
    )
    est = av._otel_estimate(f)
    assert est.present is True
    assert est.cost_usd == pytest.approx(4.0)


def test_otel_estimate_tokens_only_is_absent(tmp_path, monkeypatch) -> None:
    data_dir = _otel_env(tmp_path, monkeypatch)
    f = data_dir / "otel_export.jsonl"
    f.write_text(
        json.dumps(
            {"metric": "claude_code.token.usage", "value": 1000, "attributes": {"type": "input"}}
        ),
        encoding="utf-8",
    )
    assert av._otel_estimate(f).present is False  # saw_cost is False


def test_analyze_value_attribution_divergence(env, pricing, tmp_path) -> None:
    # m1 is inside d1's window (A1 attributes it); m2 is OUTSIDE every window
    # (A1 drops it) but the un-windowed baseline counts it -> baseline > A1.
    _insert_discussion(env.db_path, "d1", "2026-06-01T09:00:00Z", "2026-06-01T11:00:00Z")
    _write_transcript(
        env.projects_root,
        env.project_root,
        [
            _msg_line("m1", "2026-06-01T10:00:00Z", "claude-opus-4-7", input_tokens=1000),
            _msg_line("m2", "2026-06-01T14:00:00Z", "claude-opus-4-7", input_tokens=1000),
        ],
    )
    ac.analyze_cost(db_path=env.db_path, project_root=env.project_root, pricing=pricing)
    fee_file = tmp_path / "sub.yaml"
    fee_file.write_text("monthly_fee_usd: 20.0\n", encoding="utf-8")
    result = av.analyze_value(
        db_path=env.db_path,
        project_root=env.project_root,
        subscription_path=fee_file,
        otel_path=tmp_path / "none.jsonl",
        pricing=pricing,
    )
    assert result["leverage"].configured is True
    assert result["leverage"].leverage_cumulative is not None
    attr = result["attribution"]
    assert attr.available is True
    assert attr.direction == "ours_lower"  # A1 attributed fewer tokens than exist
    assert attr.flaw_class == "attribution"
    assert result["pricing"].available is False  # no OTel file


def test_analyze_value_leverage_unconfigured_without_fee(env, pricing, tmp_path) -> None:
    _insert_discussion(env.db_path, "d1", "2026-06-01T09:00:00Z", "2026-06-01T11:00:00Z")
    _write_transcript(
        env.projects_root,
        env.project_root,
        [_msg_line("m1", "2026-06-01T10:00:00Z", "claude-opus-4-7", input_tokens=1000)],
    )
    ac.analyze_cost(db_path=env.db_path, project_root=env.project_root, pricing=pricing)
    result = av.analyze_value(
        db_path=env.db_path,
        project_root=env.project_root,
        subscription_path=tmp_path / "missing.yaml",
        otel_path=tmp_path / "none.jsonl",
        pricing=pricing,
    )
    assert result["leverage"].configured is False
    assert "not configured" in result["leverage"].reason


def test_analyze_value_missing_db_returns_empty(tmp_path, pricing) -> None:
    result = av.analyze_value(
        db_path=tmp_path / "nope.db",
        subscription_path=tmp_path / "none.yaml",
        otel_path=tmp_path / "none.jsonl",
        pricing=pricing,
    )
    assert result["leverage"] is None


@pytest.mark.regression
def test_a3_persists_no_dollar_or_ratio(env, pricing, tmp_path) -> None:
    # ADR-0013 compute-don't-store: A3 derives every dollar/ratio at read and
    # persists NOTHING. Guard: analyze_value writes no row to any table and adds
    # no A3-specific table. Would fail if a future change cached a leverage/
    # divergence figure in the DB.
    _insert_discussion(env.db_path, "d1", "2026-06-01T09:00:00Z", "2026-06-01T11:00:00Z")
    _write_transcript(
        env.projects_root,
        env.project_root,
        [_msg_line("m1", "2026-06-01T10:00:00Z", "claude-opus-4-7", input_tokens=1000)],
    )
    ac.analyze_cost(db_path=env.db_path, project_root=env.project_root, pricing=pricing)
    before = _table_row_counts(env.db_path)
    fee_file = tmp_path / "sub.yaml"
    fee_file.write_text("monthly_fee_usd: 20.0\n", encoding="utf-8")
    av.analyze_value(
        db_path=env.db_path,
        project_root=env.project_root,
        subscription_path=fee_file,
        otel_path=tmp_path / "none.jsonl",
        pricing=pricing,
    )
    after = _table_row_counts(env.db_path)
    assert before == after  # read-only: not one row written anywhere
    assert not any(
        ("value" in t or "leverage" in t or "subscription" in t) for t in after
    )  # no A3-specific table was created


def test_window_months_zero_span_is_none() -> None:
    from datetime import UTC, datetime

    ts = datetime(2026, 1, 1, tzinfo=UTC)
    assert av._window_months({"a": _msg_record(ts), "b": _msg_record(ts)}) is None


def test_analyze_value_prints_labelled_report(env, pricing, tmp_path, capsys) -> None:
    # The AC: the leverage line must carry coverage% AND a labelled time basis.
    _insert_discussion(env.db_path, "d1", "2026-06-01T09:00:00Z", "2026-06-01T15:00:00Z")
    _write_transcript(
        env.projects_root,
        env.project_root,
        [
            _msg_line("m1", "2026-06-01T10:00:00Z", "claude-opus-4-7", input_tokens=1000),
            _msg_line("m2", "2026-06-01T14:00:00Z", "claude-sonnet-4-6", output_tokens=500),
        ],
    )
    ac.analyze_cost(db_path=env.db_path, project_root=env.project_root, pricing=pricing)
    fee_file = tmp_path / "sub.yaml"
    fee_file.write_text("monthly_fee_usd: 20.0\n", encoding="utf-8")
    av.analyze_value(
        db_path=env.db_path,
        project_root=env.project_root,
        subscription_path=fee_file,
        otel_path=tmp_path / "none.jsonl",
        pricing=pricing,
    )
    out = capsys.readouterr().out
    assert "List-price-equivalent vs subscription" in out
    assert "coverage" in out  # coverage% carried
    assert "/monthly" in out  # fee period labelled
    assert "per-month multiple" in out  # the apples-to-apples figure leads
    assert "cumulative over the window" in out  # time basis labelled
    assert "Estimate cross-check - attribution" in out
    assert "Estimate cross-check - pricing (OpenTelemetry)" in out
    assert "not yet active" in out  # OTel absent -> enable-affordance, not a dead row


def test_print_divergence_surfaces_independent_cost_when_unavailable(capsys) -> None:
    # Zero-denominator: unavailable, but the independent source's reported cost
    # is still surfaced (the "(independent source reported $0.00)" line).
    ind = IndependentEstimate(
        present=True,
        cost_usd=0.0,
        token_basis=0,
        source_label="base",
        scope_coverage_pct=0.0,
        flaw_class=FLAW_ATTRIBUTION,
    )
    result = cross_check(_report(666.0), ind)
    av._print_divergence("Estimate cross-check - attribution", result)
    out = capsys.readouterr().out
    assert "unavailable" in out
    assert "independent source reported $0.00" in out


def test_analyze_value_unconfigured_leverage_prints_absence(
    env, pricing, tmp_path, capsys
) -> None:
    _insert_discussion(env.db_path, "d1", "2026-06-01T09:00:00Z", "2026-06-01T11:00:00Z")
    _write_transcript(
        env.projects_root,
        env.project_root,
        [_msg_line("m1", "2026-06-01T10:00:00Z", "claude-opus-4-7", input_tokens=1000)],
    )
    ac.analyze_cost(db_path=env.db_path, project_root=env.project_root, pricing=pricing)
    av.analyze_value(
        db_path=env.db_path,
        project_root=env.project_root,
        subscription_path=tmp_path / "missing.yaml",
        otel_path=tmp_path / "none.jsonl",
        pricing=pricing,
    )
    out = capsys.readouterr().out
    assert "list-price-equivalent multiple: n/a - subscription fee not configured" in out
    assert "A1 cost so far" in out


def test_baseline_estimate_empty_messages_is_absent(pricing) -> None:
    est = av._baseline_estimate({}, pricing)
    assert est.present is False
    assert est.cost_usd is None
    assert cross_check(_report(666.0), est).available is False


def test_otel_estimate_negative_cost_flows_to_absent(tmp_path, monkeypatch) -> None:
    # A negative reported cost is present-but-unusable: the source ran, but the
    # divergence is absent (zero/negative denominator), never a fabricated number.
    data_dir = _otel_env(tmp_path, monkeypatch)
    f = data_dir / "otel_export.jsonl"
    f.write_text(json.dumps({"metric": "claude_code.cost.usage", "value": -5.0}), encoding="utf-8")
    est = av._otel_estimate(f)
    assert est.present is True
    assert est.cost_usd == pytest.approx(-5.0)
    res = cross_check(_report(10.0), est)
    assert res.available is False
    assert res.divergence_pct is None
    assert "zero or negative" in res.reason


@pytest.mark.regression
def test_analyze_value_since_skips_attribution_crosscheck(env, pricing, tmp_path) -> None:
    # Review BLOCKING (independent-perspective): A1 is loaded all-time from the
    # stored breakdown, but the live baseline honours --since. Comparing them
    # would divide two different token populations and print a false divergence.
    # With since set, the attribution cross-check must report typed absence.
    from datetime import UTC, datetime

    _insert_discussion(env.db_path, "d1", "2026-06-01T09:00:00Z", "2026-06-01T11:00:00Z")
    _write_transcript(
        env.projects_root,
        env.project_root,
        [_msg_line("m1", "2026-06-01T10:00:00Z", "claude-opus-4-7", input_tokens=1000)],
    )
    ac.analyze_cost(db_path=env.db_path, project_root=env.project_root, pricing=pricing)
    result = av.analyze_value(
        db_path=env.db_path,
        project_root=env.project_root,
        since=datetime(2026, 6, 1, tzinfo=UTC),
        subscription_path=tmp_path / "none.yaml",
        otel_path=tmp_path / "none.jsonl",
        pricing=pricing,
    )
    attr = result["attribution"]
    assert attr.available is False  # not a fabricated divergence
    assert "since" in (attr.source_label or "").lower()


# --------------------------------------------------------------------------- #
# Layer B — dashboard (render-only over the A1/A2/A3 read-side outputs)
# --------------------------------------------------------------------------- #


def _populate_dashboard_db(env, pricing: PricingTable, tmp_path: Path) -> tuple[Path, Path]:
    """Populate the DB with A1 cost + A2 failures via the WRITE-side analyzers.

    Setup-only use of the write-side analyzers (the dashboard itself never calls
    them). Writes a session with a 3x Bash retry loop + an orphaned Agent
    dispatch within d1's window so both cost rows and failure rows exist.
    Returns ``(subscription_path, otel_path)`` — the otel path is absent.
    """
    _insert_discussion(env.db_path, "d1", "2026-01-01T00:00:00Z", "2026-01-01T02:00:00Z")
    main = [
        _assistant_line(
            "m1",
            "2026-01-01T00:00:01Z",
            "claude-opus-4-7",
            [("t1", "Bash", {"c": "ls"})],
            output_tokens=1000,
        ),
        _result_line("2026-01-01T00:00:02Z", "t1"),
        _assistant_line(
            "m2",
            "2026-01-01T00:00:03Z",
            "claude-opus-4-7",
            [("t2", "Bash", {"c": "ls"})],
            output_tokens=1000,
        ),
        _result_line("2026-01-01T00:00:04Z", "t2"),
        _assistant_line(
            "m3",
            "2026-01-01T00:00:05Z",
            "claude-opus-4-7",
            [("t3", "Bash", {"c": "ls"})],
            output_tokens=1000,
        ),
        _result_line("2026-01-01T00:00:06Z", "t3"),
        _assistant_line(
            "m4",
            "2026-01-01T01:00:00Z",
            "claude-opus-4-7",
            [("t4", "Agent", {"subagent_type": "qa"})],
        ),
    ]
    _write_session(env.projects_root, env.project_root, "sess1", main)
    ac.analyze_cost(
        db_path=env.db_path, project_root=env.project_root, full_rescan=True, pricing=pricing
    )
    af.analyze_failures(db_path=env.db_path, full_rescan=True, pricing=pricing)
    fee_file = tmp_path / "sub.yaml"
    fee_file.write_text("monthly_fee_usd: 20.0\nplan_label: Test Plan\n", encoding="utf-8")
    return fee_file, tmp_path / "no_otel.jsonl"


def _schema_snapshot(db_path: Path) -> list[str]:
    """Snapshot every object's DDL from sqlite_master (proves no schema change)."""
    conn = sqlite3.connect(str(db_path))
    try:
        return sorted(
            r[0] for r in conn.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL")
        )
    finally:
        conn.close()


# --- DashboardData builders for pure render tests -------------------------- #


def _lev_configured() -> LeverageResult:
    return leverage(_report(100.0), SubscriptionFee(monthly_fee_usd=20.0), window_months=2.0)


def _lev_absent() -> LeverageResult:
    return leverage(_report(100.0), None)


def _div_attribution_available() -> DivergenceResult:
    indep = IndependentEstimate(
        present=True,
        cost_usd=100.0,
        token_basis=1000,
        source_label="attribution-baseline",
        scope_coverage_pct=100.0,
        flaw_class=FLAW_ATTRIBUTION,
    )
    return cross_check(_report(50.0), indep)


def _div_otel_absent() -> DivergenceResult:
    indep = IndependentEstimate(
        present=False,
        cost_usd=None,
        token_basis=0,
        source_label="otel",
        scope_coverage_pct=0.0,
        flaw_class=FLAW_PRICING,
    )
    return cross_check(_report(50.0), indep)


def _div_otel_available() -> DivergenceResult:
    indep = IndependentEstimate(
        present=True,
        cost_usd=40.0,
        token_basis=1000,
        source_label="otel (claude_code.cost.usage)",
        scope_coverage_pct=100.0,
        flaw_class=FLAW_PRICING,
    )
    return cross_check(_report(50.0), indep)


def _data(
    *,
    cost_report: CostReport | None = None,
    cost_state: str = STATE_DATA,
    failures: list[RankedFailure] | None = None,
    failures_state: str = STATE_DATA,
    leverage_result: LeverageResult | None = None,
    attribution: DivergenceResult | None = None,
    pricing_check: DivergenceResult | None = None,
) -> DashboardData:
    return DashboardData(
        cost_report=cost_report if cost_report is not None else _report(10.0),
        cost_state=cost_state,
        failures=failures if failures is not None else [],
        failures_state=failures_state,
        leverage=leverage_result if leverage_result is not None else _lev_configured(),
        attribution=attribution if attribution is not None else _div_attribution_available(),
        pricing_check=pricing_check if pricing_check is not None else _div_otel_absent(),
        generated_label="2026-06-07 07:30 UTC",
    )


# --- assembly seam: fidelity + read-side-only + no-persistence ------------- #


def test_assemble_dashboard_data_matches_read_side(env, pricing, tmp_path) -> None:
    # Transport-fidelity: assemble_dashboard_data must equal build_cost_report /
    # rank_failures / analyze_value field-for-field on the same fixture.
    fee, otel = _populate_dashboard_db(env, pricing, tmp_path)
    data = dash.assemble_dashboard_data(
        env.db_path,
        pricing=pricing,
        subscription_path=fee,
        otel_path=otel,
        project_root=env.project_root,
    )
    # Reference uses the SAME read-side path on a read-only connection (qa A8):
    # assemble_value_inputs, not analyze_value (which calls init_db — a write-side
    # asymmetry that would compare a freshly-initialized DB against the ro view).
    conn = sqlite3.connect(f"file:{env.db_path.as_posix()}?mode=ro", uri=True)
    try:
        ref_cost = build_cost_report(ac.load_cost_rows(conn), pricing)
        ref_ranked = rank_failures(af.load_failure_signals(conn), pricing)
        ref_value = av.assemble_value_inputs(
            conn,
            pricing=pricing,
            project_root=env.project_root,
            since=None,
            subscription_path=fee,
            otel_path=otel,
        )
    finally:
        conn.close()
    # A1 — total, coverage, full-cover flag, and every by_tier cost.
    assert data.cost_report.total_cost_usd == ref_cost.total_cost_usd
    assert data.cost_report.coverage_pct == ref_cost.coverage_pct
    assert data.cost_report.is_fully_covered == ref_cost.is_fully_covered
    assert {t: tc.cost_usd for t, tc in data.cost_report.by_tier.items()} == {
        t: tc.cost_usd for t, tc in ref_cost.by_tier.items()
    }
    # A2 — same ranked signatures + costs.
    assert [(r.signal.signature, r.cost_usd) for r in data.failures] == [
        (r.signal.signature, r.cost_usd) for r in ref_ranked
    ]
    assert data.failures  # the fixture produced at least one signal
    # A3 — leverage + both divergences.
    assert data.leverage.configured == ref_value["leverage"].configured
    assert data.leverage.leverage_cumulative == ref_value["leverage"].leverage_cumulative
    assert data.leverage.leverage_per_month == ref_value["leverage"].leverage_per_month
    assert data.attribution.available == ref_value["attribution"].available
    assert data.attribution.divergence_pct == ref_value["attribution"].divergence_pct
    assert data.attribution.direction == ref_value["attribution"].direction
    assert data.pricing_check.available == ref_value["pricing"].available
    assert data.pricing_check.divergence_pct == ref_value["pricing"].divergence_pct  # qa A5
    assert data.pricing_check.direction == ref_value["pricing"].direction  # qa A5


@pytest.mark.regression
def test_dashboard_never_calls_writeside_or_init_db(env, pricing, tmp_path, monkeypatch) -> None:
    # Read-side-only: the dashboard path must never invoke analyze_cost /
    # analyze_failures / init_db (all of which mutate the DB).
    fee, otel = _populate_dashboard_db(env, pricing, tmp_path)
    calls: list[str] = []
    monkeypatch.setattr(ac, "analyze_cost", lambda *a, **k: calls.append("analyze_cost"))
    monkeypatch.setattr(af, "analyze_failures", lambda *a, **k: calls.append("analyze_failures"))
    monkeypatch.setattr(av, "init_db", lambda *a, **k: calls.append("init_db"))
    dash.assemble_dashboard_data(
        env.db_path,
        pricing=pricing,
        subscription_path=fee,
        otel_path=otel,
        project_root=env.project_root,
    )
    assert calls == []
    # And the transport module never even imported the mutating entry points.
    assert not hasattr(dash, "analyze_cost")
    assert not hasattr(dash, "analyze_failures")
    assert not hasattr(dash, "init_db")


@pytest.mark.regression
def test_dashboard_persists_nothing(env, pricing, tmp_path) -> None:
    # Strong no-persistence: schema (sqlite_master) AND row counts unchanged.
    fee, otel = _populate_dashboard_db(env, pricing, tmp_path)
    before_counts = _table_row_counts(env.db_path)
    before_schema = _schema_snapshot(env.db_path)
    dash.assemble_dashboard_data(
        env.db_path,
        pricing=pricing,
        subscription_path=fee,
        otel_path=otel,
        project_root=env.project_root,
    )
    assert _table_row_counts(env.db_path) == before_counts
    assert _schema_snapshot(env.db_path) == before_schema


@pytest.mark.regression
def test_dashboard_connection_is_readonly(env) -> None:
    # The DB is opened file:...?mode=ro — a write must be refused at the driver.
    conn = dash._connect_readonly(env.db_path)
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("CREATE TABLE _should_fail (x)")
    finally:
        conn.close()


# --- honest-absence states (one test per state) ---------------------------- #


@pytest.mark.regression
def test_absence_fee_not_configured_renders_distinct_tile(pricing) -> None:
    html = render_dashboard_html(_data(leverage_result=_lev_absent()))
    assert 'data-state="absent"' in html
    assert "tile--absent" in html
    assert "List-price-equivalent multiple" in html  # labelled, not a 0 multiple
    assert "subscription fee not configured" in html  # the honest reason
    assert "0.00x" not in html.split("Value vs Subscription")[1].split("Attribution")[0]


@pytest.mark.regression
def test_absence_otel_not_active_renders_live_link(pricing) -> None:
    html = render_dashboard_html(_data(pricing_check=_div_otel_absent()))
    assert 'href="https://code.claude.com/docs/en/monitoring-usage"' in html
    assert 'target="_blank"' in html
    assert "enable OTel" in html


def test_absence_attribution_unavailable_renders_absence_not_zero(pricing) -> None:
    dv = DivergenceResult(
        available=False,
        our_cost_usd=50.0,
        independent_cost_usd=None,
        delta_usd=None,
        divergence_pct=None,
        direction=None,
        flaw_class=None,
        scope_coverage_pct=None,
        source_label="attribution baseline skipped: --since filters the live baseline",
        reason="no independent estimate available",
    )
    html = render_dashboard_html(_data(attribution=dv))
    # Distinct absence container + honest copy, never a fabricated 0%.
    assert html.count('data-state="absent"') >= 1
    assert "no independent estimate available" in html


@pytest.mark.regression
def test_failures_not_run_distinct_from_true_zero(pricing) -> None:
    not_run = render_dashboard_html(_data(failures=[], failures_state=STATE_NOT_RUN))
    true_zero = render_dashboard_html(_data(failures=[], failures_state=STATE_DATA))
    # not-run: a distinct absence tile pointing at the analyzer.
    assert "analyze_failures.py" in not_run
    assert 'data-state="absent"' in not_run
    # true-zero: a normal DATA tile with explicit copy, NOT the absence style.
    assert "No failure signals detected" in true_zero
    assert "No failure signals detected" not in not_run
    assert "analyze_failures.py" not in true_zero


@pytest.mark.regression
def test_unknown_tier_rendered_uncosted_not_zero(pricing) -> None:
    rows = [
        ModelTokenRow("d", "claude-opus-4-7", "opus", tokens_in=1_000),
        ModelTokenRow("d", "some-other-llm", UNKNOWN_TIER, tokens_in=1_000),
    ]
    report = build_cost_report(rows, pricing)
    html = render_dashboard_html(_data(cost_report=report, cost_state=STATE_DATA))
    assert "uncosted" in html  # the unknown tier is uncosted, never $0
    assert 'class="uncosted"' in html


def test_empty_db_renders_every_panel_in_absence(env, pricing) -> None:
    # First-run / empty DB: every panel renders its absence state, no crash.
    data = dash.assemble_dashboard_data(
        env.db_path, pricing=pricing, project_root=env.project_root
    )
    assert data.cost_state == STATE_NOT_RUN
    assert data.failures_state == STATE_NOT_RUN
    assert data.leverage.configured is False  # no fee
    assert data.attribution.available is False  # no transcripts
    assert data.pricing_check.available is False  # no otel
    html = render_dashboard_html(data)
    assert "<!DOCTYPE html>" in html
    assert html.count('data-state="absent"') >= 4  # cost, failures, leverage, otel(+attribution)


def test_true_zero_vs_not_run_state_classification(env, pricing) -> None:
    # Empty telemetry_failures + a failures watermark => true zero (data tile);
    # empty + no watermark => analyzer-not-yet-run (absence).
    conn = sqlite3.connect(str(env.db_path))
    try:
        conn.execute(
            "INSERT INTO telemetry_run_state (key, value, updated_at) "
            "VALUES ('failures_last_analyzed_mtime', '123.0', '2026-01-01T00:00:00Z')"
        )
        conn.commit()
    finally:
        conn.close()
    data = dash.assemble_dashboard_data(
        env.db_path, pricing=pricing, project_root=env.project_root
    )
    assert data.failures == [] and data.failures_state == STATE_DATA  # true zero


# --- escaping (C6) --------------------------------------------------------- #

_XSS = "<script>alert('telemetry-xss')</script>"


@pytest.mark.regression
@pytest.mark.parametrize("field", ["signature", "detail"])
def test_failure_string_fields_are_escaped(field) -> None:
    # The transcript tool-name feeds FailureSignal.signature; both it and detail
    # are transcript-shaped and must be escaped, never live markup.
    sig = FailureSignal(
        failure_type="retry_loop",
        signature=_XSS if field == "signature" else "Bash:abc",
        occurrence_count=3,
        tier="opus",
        detail=_XSS if field == "detail" else "Bash called 3x identically",
    )
    html = render_dashboard_html(_data(failures=[RankedFailure(signal=sig, cost_usd=1.0)]))
    assert _XSS not in html
    assert "&lt;script&gt;" in html
    assert "innerHTML" not in html  # rendered as escaped text, never raw innerHTML


@pytest.mark.regression
def test_divergence_reason_is_escaped() -> None:
    dv = DivergenceResult(
        available=False,
        our_cost_usd=50.0,
        independent_cost_usd=None,
        delta_usd=None,
        divergence_pct=None,
        direction=None,
        flaw_class=None,
        scope_coverage_pct=None,
        source_label="x",
        reason=_XSS,
    )
    html = render_dashboard_html(_data(attribution=dv))
    assert _XSS not in html
    assert "&lt;script&gt;" in html


@pytest.mark.regression
def test_divergence_source_label_is_escaped() -> None:
    dv = DivergenceResult(
        available=True,
        our_cost_usd=50.0,
        independent_cost_usd=100.0,
        delta_usd=-50.0,
        divergence_pct=-50.0,
        direction="ours_lower",
        flaw_class=FLAW_ATTRIBUTION,
        scope_coverage_pct=100.0,
        source_label=_XSS,
        reason="",
    )
    html = render_dashboard_html(_data(attribution=dv))
    assert _XSS not in html
    assert "&lt;script&gt;" in html


# --- no-slug (C2) ---------------------------------------------------------- #


@pytest.mark.regression
def test_no_slug_or_env_leak_on_no_db_path(tmp_path, monkeypatch, capsys) -> None:
    # Behavioral: inject a fake NTFY_TOPIC, force the no-DB path, assert the slug
    # never appears in stdout/stderr. The generator imports no notify module.
    monkeypatch.setenv("NTFY_TOPIC", "secret-slug-do-not-print")
    monkeypatch.setattr(dash, "DB_PATH", tmp_path / "absent.db")
    monkeypatch.setattr(dash.sys, "argv", ["dashboard.py", "--no-open"])
    dash.main()
    captured = capsys.readouterr()
    assert "secret-slug-do-not-print" not in captured.out
    assert "secret-slug-do-not-print" not in captured.err
    assert not hasattr(dash, "notify")


@pytest.mark.regression
def test_assemble_on_missing_db_raises_without_leaking_slug(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("NTFY_TOPIC", "secret-slug-do-not-print")
    with pytest.raises(sqlite3.OperationalError):
        dash.assemble_dashboard_data(tmp_path / "absent.db", pricing=parse_pricing(PRICING_DATA))
    captured = capsys.readouterr()
    assert "secret-slug-do-not-print" not in (captured.out + captured.err)


# --- ASCII console summary (C7) -------------------------------------------- #


@pytest.mark.parametrize(
    "factory",
    [
        lambda: _data(),  # all present
        lambda: _data(leverage_result=_lev_absent()),  # fee not configured
        lambda: _data(failures=[], failures_state=STATE_DATA),  # no failures
        lambda: _data(cost_state=STATE_NOT_RUN, failures_state=STATE_NOT_RUN),  # not run
    ],
)
@pytest.mark.regression
def test_console_summary_is_ascii_across_states(factory) -> None:
    lines = render_console_summary(factory(), output_path="C:/tmp/telemetry_dashboard.html")
    text = "\n".join(lines)
    text.encode("ascii")  # must not raise
    text.encode("cp1252")  # must not raise (the cp1252 regression-ledger class)
    assert 5 <= len(lines) <= 6


# --- plain-language framing (R2a) ------------------------------------------ #


def test_plain_language_legends_present(pricing) -> None:
    report = build_cost_report(
        [ModelTokenRow("d", "claude-opus-4-7", "opus", tokens_in=1_000)], pricing
    )
    html = render_dashboard_html(
        _data(cost_report=report, cost_state=STATE_DATA, leverage_result=_lev_configured())
    )
    assert "pay-per-use" in html  # A1 legend
    assert "List-price-equivalent multiple" in html  # A3 primary label
    assert "monthly subscription fee" in html  # A3 legend gloss


# --- main() generate + --no-open (R1/R4/R6) -------------------------------- #


def test_main_no_open_writes_file_without_opening(
    env, pricing, tmp_path, monkeypatch, capsys
) -> None:
    fee, otel = _populate_dashboard_db(env, pricing, tmp_path)
    monkeypatch.setattr(dash, "DB_PATH", env.db_path)
    monkeypatch.setattr(dash.tempfile, "gettempdir", lambda: str(tmp_path))
    opened: list[str] = []
    monkeypatch.setattr(dash.webbrowser, "open", lambda u: opened.append(u))
    monkeypatch.setattr(dash.sys, "argv", ["dashboard.py", "--no-open"])
    dash.main()
    out_file = tmp_path / dash.DASHBOARD_FILENAME
    assert out_file.exists()
    assert "<!DOCTYPE html>" in out_file.read_text(encoding="utf-8")
    assert opened == []  # --no-open suppressed the browser
    assert "Dashboard:" in capsys.readouterr().out


def test_main_opens_browser_without_no_open(env, pricing, tmp_path, monkeypatch) -> None:
    _populate_dashboard_db(env, pricing, tmp_path)
    monkeypatch.setattr(dash, "DB_PATH", env.db_path)
    monkeypatch.setattr(dash.tempfile, "gettempdir", lambda: str(tmp_path))
    opened: list[str] = []
    monkeypatch.setattr(dash.webbrowser, "open", lambda u: opened.append(u))
    monkeypatch.setattr(dash.sys, "argv", ["dashboard.py"])
    dash.main()
    assert len(opened) == 1  # browser opened exactly once


def test_pricing_cross_check_available_renders_divergence() -> None:
    html = render_dashboard_html(_data(pricing_check=_div_otel_available()))
    # our 50 vs independent 40 -> ours higher; the divergence sentence + source.
    assert "higher than" in html
    assert "claude_code.cost.usage" in html


def test_leverage_configured_window_unknown_shows_cumulative() -> None:
    lev = leverage(_report(100.0), SubscriptionFee(monthly_fee_usd=20.0))  # no window
    html = render_dashboard_html(_data(leverage_result=lev))
    assert "5.00x" in html  # cumulative 100/20, shown as the primary
    assert "cost window unknown" in html


def test_console_summary_cumulative_only_and_not_run_lines() -> None:
    lev = leverage(_report(100.0), SubscriptionFee(monthly_fee_usd=20.0))  # no per-month
    cum = render_console_summary(
        _data(leverage_result=lev), output_path="C:/tmp/telemetry_dashboard.html"
    )
    assert any("cumulative" in line for line in cum)
    not_run = render_console_summary(
        _data(cost_state=STATE_NOT_RUN, failures_state=STATE_NOT_RUN),
        output_path="C:/tmp/telemetry_dashboard.html",
    )
    assert any("Cost: analyzer not yet run" in line for line in not_run)
    assert any("Failures: analyzer not yet run" in line for line in not_run)


# --- review B1: leverage must not fabricate a 0.00x when cost is not measured -- #


@pytest.mark.regression
def test_leverage_absent_when_cost_not_run_even_if_fee_configured() -> None:
    # Review BLOCKING B1 (independent-perspective): a configured fee on a DB whose
    # cost analyzer has not run must NOT render an authoritative 0.00x leverage —
    # the numerator was never measured. Before the fix this rendered a 0.00x data
    # subtile; after, it renders the cost-not-measured absence tile.
    lev = leverage(_report(0.0, total_tokens=0), SubscriptionFee(monthly_fee_usd=20.0))
    html = render_dashboard_html(_data(leverage_result=lev, cost_state=STATE_NOT_RUN))
    value_panel = html.split("Value vs Subscription")[1]
    assert "0.00x" not in value_panel  # no fabricated multiple
    assert "List-price-equivalent multiple" in value_panel
    assert "analyze_cost.py" in value_panel  # honest action
    assert 'data-state="absent"' in value_panel


@pytest.mark.regression
def test_console_leverage_not_fabricated_when_cost_not_run() -> None:
    lev = leverage(_report(0.0, total_tokens=0), SubscriptionFee(monthly_fee_usd=20.0))
    lines = render_console_summary(
        _data(leverage_result=lev, cost_state=STATE_NOT_RUN),
        output_path="C:/tmp/telemetry_dashboard.html",
    )
    text = "\n".join(lines)
    assert "0.00x" not in text
    assert "cost not yet measured" in text


@pytest.mark.regression
def test_cost_panel_not_run_renders_absence_not_zero() -> None:
    # qa A4: the A1 cost-panel STATE_NOT_RUN render path must be a distinct absence
    # tile pointing at the analyzer, never a fabricated $0.00.
    html = render_dashboard_html(
        _data(cost_report=_report(0.0, total_tokens=0), cost_state=STATE_NOT_RUN)
    )
    cost_panel = html.split("Failure")[0]  # everything before the failures panel
    assert 'data-state="absent"' in cost_panel
    assert "analyze_cost.py" in cost_panel
    assert "$0.00" not in cost_panel


def test_leverage_under_coverage_note_when_partial() -> None:
    # Review A3 (independent Scenario 2): a partial-coverage leverage carries a
    # prominent "computed on X%" note, not just the kv-list coverage figure.
    rep = CostReport(by_tier={}, total_cost_usd=100.0, known_tokens=700, total_tokens=1000)
    lev = leverage(rep, SubscriptionFee(monthly_fee_usd=20.0), window_months=2.0)
    html = render_dashboard_html(_data(cost_report=rep, leverage_result=lev))
    assert "Computed on 70.0% of billable tokens" in html


@pytest.mark.regression
@pytest.mark.parametrize("field", ["note", "reason"])
def test_leverage_string_fields_escaped(field) -> None:
    # qa A6 / C6: LeverageResult.reason (+ .note via basis) are escape targets.
    if field == "reason":
        lev = LeverageResult(
            configured=False,
            total_cost_usd=0.0,
            coverage_pct=0.0,
            monthly_fee_usd=None,
            window_months=None,
            fee_period="monthly",
            leverage_cumulative=None,
            leverage_per_month=None,
            reason=_XSS,
        )
    else:  # note flows into `basis` in the window-unknown branch
        lev = LeverageResult(
            configured=True,
            total_cost_usd=100.0,
            coverage_pct=100.0,
            monthly_fee_usd=20.0,
            window_months=None,
            fee_period="monthly",
            leverage_cumulative=5.0,
            leverage_per_month=None,
            note=_XSS,
        )
    html = render_dashboard_html(_data(leverage_result=lev, cost_state=STATE_DATA))
    assert _XSS not in html
    assert "&lt;script&gt;" in html


@pytest.mark.regression
def test_cost_tier_name_key_is_escaped(pricing) -> None:
    # qa A6 / C6: tier-name keys are escaped (a model id could resolve to an odd
    # string). Build a report whose by_tier carries a script-shaped tier key.
    rep = build_cost_report([ModelTokenRow("d", "m", _XSS, tokens_in=1000)], parse_pricing({}))
    html = render_dashboard_html(_data(cost_report=rep, cost_state=STATE_DATA))
    assert _XSS not in html
    assert "&lt;script&gt;" in html


def test_pricing_cross_check_generic_absent_branch(pricing) -> None:
    # qa A7: a non-OTel unavailable pricing source renders a plain absence tile,
    # NOT the OTel enable link.
    dv = DivergenceResult(
        available=False,
        our_cost_usd=50.0,
        independent_cost_usd=None,
        delta_usd=None,
        divergence_pct=None,
        direction=None,
        flaw_class=None,
        scope_coverage_pct=None,
        source_label="future-source",
        reason="not configured",
    )
    html = render_dashboard_html(_data(pricing_check=dv))
    assert 'data-state="absent"' in html
    assert "monitoring-usage" not in html  # no OTel link for a non-otel source


def test_attribution_zero_denominator_renders_absence(pricing) -> None:
    # Review A2 (ux): defense-in-depth render guard — available=True but a falsy
    # independent cost must render absence, never "0.0% covered".
    dv = DivergenceResult(
        available=True,
        our_cost_usd=50.0,
        independent_cost_usd=0.0,
        delta_usd=50.0,
        divergence_pct=None,
        direction=None,
        flaw_class=FLAW_ATTRIBUTION,
        scope_coverage_pct=100.0,
        source_label="attribution-baseline",
        reason="",
    )
    html = render_dashboard_html(_data(attribution=dv))
    assert "0.0% covered" not in html
    assert 'data-state="absent"' in html


# --------------------------------------------------------------------------- #
# live.py — pure event-fold (SPEC-20260607-183136 R14/AC14)
# --------------------------------------------------------------------------- #


def _ts(seconds: int) -> datetime:
    """Build a deterministic UTC timestamp ``seconds`` past 2026-06-07 12:00.

    Accepts any non-negative integer (incl. ``seconds > 59``) — overflow is
    distributed across minutes so cap-boundary tests can use ``range(101)``
    without hand-rolling minute math.
    """
    base = datetime(2026, 6, 7, 12, 0, 0, tzinfo=UTC)
    return base + timedelta(seconds=seconds)


def _msg_event(
    seconds: int,
    lane: str,
    model: str | None,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read: int = 0,
    cache_create: int = 0,
    agent_type: str | None = None,
) -> LiveEvent:
    return LiveEvent(
        kind="message",
        timestamp=_ts(seconds),
        lane_id=lane,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read,
        cache_create_tokens=cache_create,
        agent_type=agent_type,
    )


def _dispatch_event(seconds: int, lane: str, agent_type: str | None = None) -> LiveEvent:
    return LiveEvent(
        kind="dispatch",
        timestamp=_ts(seconds),
        lane_id=lane,
        agent_type=agent_type,
        tool_name="Agent",
    )


def _result_event(seconds: int, ref_id: str, *, lane: str = "main") -> LiveEvent:
    return LiveEvent(kind="result", timestamp=_ts(seconds), lane_id=lane, ref_id=ref_id)


def _context_event(seconds: int, current: int, window: int) -> LiveEvent:
    return LiveEvent(
        kind="context",
        timestamp=_ts(seconds),
        lane_id="main",
        context_tokens=current,
        context_window=window,
    )


# qa F2 — empty inputs.
def test_fold_events_empty_returns_clean_state(pricing: PricingTable) -> None:
    state = fold_events([], pricing)
    assert state.main is None
    assert state.agents == ()
    assert state.total_cost_usd == 0.0
    assert state.recent_events == ()
    assert state.main_turns_seen == 0
    assert state.uncosted_turns == 0
    assert state.runway.est_turns_remaining is None
    assert state.runway.status == RUNWAY_OK


def test_fold_basic_main_lane_costs_match_pricing(pricing: PricingTable) -> None:
    # opus rate: 15 $/Mtok in, 75 $/Mtok out -> 1000 in + 500 out = 0.015 + 0.0375 = 0.0525.
    state = fold_events(
        [_msg_event(0, "main", "claude-opus-4-7", input_tokens=1000, output_tokens=500)],
        pricing,
    )
    assert state.main is not None
    assert state.main.status == LANE_ACTIVE
    assert state.main.input_tokens == 1000
    assert state.main.output_tokens == 500
    assert state.main.cost_usd == pytest.approx(0.0525)
    assert state.total_cost_usd == pytest.approx(0.0525)
    assert state.main_turns_seen == 1
    assert state.main_turn_output_tokens == 500
    assert state.uncosted_turns == 0


# qa F3 — model=None / unknown tier: tokens accrue, cost held back.
def test_message_with_none_model_accrues_tokens_but_zero_cost(pricing: PricingTable) -> None:
    state = fold_events(
        [_msg_event(0, "main", None, input_tokens=1000, output_tokens=500)],
        pricing,
    )
    assert state.main is not None
    assert state.main.input_tokens == 1000
    assert state.main.output_tokens == 500
    assert state.main.cost_usd == 0.0
    assert state.total_cost_usd == 0.0
    assert state.uncosted_turns == 1
    # Output tokens are observable regardless of pricing — so the runway estimate
    # IS available even for an uncosted main turn (this isolates the cost-zero
    # honesty from the runway-estimate signal). 100K remaining / 500 out = 200.
    state2 = apply_event(state, _context_event(1, 100_000, 200_000), pricing)
    assert state2.runway.est_turns_remaining == 200


def test_subagent_lane_with_unknown_tier_model_is_uncosted(pricing: PricingTable) -> None:
    # qa F3 (subagent variant): the uncosted-turn path must also fire on the
    # non-main branch — a future model family that lands before pricing.yaml is
    # updated could arrive on a subagent before it ever shows up on the main lane.
    state = fold_events(
        [
            _dispatch_event(0, "tool_x", "qa-specialist"),
            _msg_event(1, "tool_x", "claude-mystery-9", input_tokens=500, output_tokens=200),
        ],
        pricing,
    )
    assert state.uncosted_turns == 1
    assert state.total_cost_usd == 0.0
    assert state.agents[0].input_tokens == 500
    assert state.agents[0].cost_usd == 0.0


def test_message_with_unknown_tier_model_is_uncosted(pricing: PricingTable) -> None:
    # The pricing fixture only knows opus + sonnet — "claude-mystery-9" misses
    # both the model map and the family substring match -> UNKNOWN_TIER.
    state = fold_events(
        [_msg_event(0, "main", "claude-mystery-9", input_tokens=500, output_tokens=200)],
        pricing,
    )
    assert state.uncosted_turns == 1
    assert state.total_cost_usd == 0.0
    assert state.main is not None
    assert state.main.input_tokens == 500  # tokens still accumulate


# qa F5 — duplicate dispatch idempotence.
def test_duplicate_dispatch_is_idempotent(pricing: PricingTable) -> None:
    state = fold_events(
        [
            _msg_event(0, "main", "claude-opus-4-7", input_tokens=100, output_tokens=50),
            _dispatch_event(1, "tool_x", "qa-specialist"),
            _dispatch_event(2, "tool_x", "qa-specialist"),  # duplicate
        ],
        pricing,
    )
    assert len(state.agents) == 1
    assert state.main is not None
    assert state.main.tool_count == 1  # NOT 2


def test_dispatch_increments_main_tool_count(pricing: PricingTable) -> None:
    state = fold_events(
        [
            _msg_event(0, "main", "claude-opus-4-7", input_tokens=100, output_tokens=50),
            _dispatch_event(1, "tool_a", "qa"),
            _dispatch_event(2, "tool_b", "security"),
        ],
        pricing,
    )
    assert len(state.agents) == 2
    assert state.main is not None
    assert state.main.tool_count == 2


# qa F6 — result no-ops.
def test_result_with_unknown_ref_id_is_noop(pricing: PricingTable) -> None:
    state = fold_events(
        [
            _msg_event(0, "main", "claude-opus-4-7", input_tokens=100, output_tokens=50),
            _dispatch_event(1, "tool_real", "qa"),
            _result_event(2, "tool_does_not_exist"),
        ],
        pricing,
    )
    assert state.agents[0].lane_id == "tool_real"
    assert state.agents[0].status == LANE_ACTIVE


def test_duplicate_result_is_idempotent(pricing: PricingTable) -> None:
    state = fold_events(
        [
            _dispatch_event(0, "tool_x", "qa"),
            _result_event(1, "tool_x"),
            _result_event(2, "tool_x"),  # duplicate
        ],
        pricing,
    )
    assert len(state.agents) == 1
    assert state.agents[0].status == LANE_COMPLETE


def test_result_transitions_subagent_lane_to_complete(pricing: PricingTable) -> None:
    state = fold_events(
        [
            _dispatch_event(0, "tool_x", "qa"),
            _msg_event(1, "tool_x", "claude-sonnet-4-6", input_tokens=2000, output_tokens=800),
            _result_event(2, "tool_x"),
        ],
        pricing,
    )
    assert state.agents[0].status == LANE_COMPLETE
    assert state.agents[0].input_tokens == 2000


# qa F7 — runway boundary values.
@pytest.mark.parametrize(
    ("fill_pct", "expected"),
    [
        (54.9, RUNWAY_OK),
        (55.0, RUNWAY_AMBER),  # inclusive boundary
        (69.9, RUNWAY_AMBER),
        (70.0, RUNWAY_RED),  # inclusive boundary
        (100.0, RUNWAY_RED),
        (0.0, RUNWAY_OK),
    ],
)
def test_runway_status_inclusive_boundaries(fill_pct: float, expected: str) -> None:
    # Imported in-body so the ruff formatter does not strip the underscore-prefixed
    # private (its top-level F401 hint flags `_name` imports as unused).
    from src.telemetry import live as live_mod

    assert live_mod._runway_status(fill_pct, RUNWAY_AMBER_DEFAULT, RUNWAY_RED_DEFAULT) == expected


def test_context_event_with_zero_window_is_safe(pricing: PricingTable) -> None:
    state = fold_events([_context_event(0, current=42, window=0)], pricing)
    assert state.runway.fill_pct == 0.0
    assert state.runway.status == RUNWAY_OK
    assert state.runway.est_turns_remaining is None


# qa F4 — est_turns_remaining honest absence on cold start + zero-avg case.
def test_est_turns_remaining_none_on_cold_start(pricing: PricingTable) -> None:
    state = fold_events([_context_event(0, current=100_000, window=200_000)], pricing)
    assert state.runway.est_turns_remaining is None


def test_est_turns_remaining_none_when_all_zero_output(pricing: PricingTable) -> None:
    state = fold_events(
        [
            _msg_event(0, "main", "claude-opus-4-7", input_tokens=500, output_tokens=0),
            _msg_event(1, "main", "claude-opus-4-7", input_tokens=500, output_tokens=0),
            _context_event(2, current=100_000, window=200_000),
        ],
        pricing,
    )
    assert state.runway.est_turns_remaining is None


def test_est_turns_remaining_uses_main_lane_only(pricing: PricingTable) -> None:
    # Arch F2: a fast Haiku-style subagent rate must NOT skew the main runway.
    # Use sonnet as a proxy for "second model on a subagent" (the pricing fixture
    # doesn't carry haiku). Main outputs avg 500 tok/turn; subagent outputs 50.
    # If the avg were session-wide it would be (500+50)/2 = 275 -> overstate
    # turns remaining; using main only gives 500 -> 200 turns.
    state = fold_events(
        [
            _msg_event(0, "main", "claude-opus-4-7", input_tokens=1000, output_tokens=500),
            _dispatch_event(1, "tool_x", "qa"),
            _msg_event(2, "tool_x", "claude-sonnet-4-6", input_tokens=1000, output_tokens=50),
            _context_event(3, current=0, window=100_000),
        ],
        pricing,
    )
    assert state.runway.est_turns_remaining == 200  # 100_000 / 500


# qa F8 — RECENT_EVENTS_CAP boundary.
def test_recent_events_capped(pricing: PricingTable) -> None:
    events = [
        _msg_event(i, "main", "claude-opus-4-7", input_tokens=1, output_tokens=1)
        for i in range(RECENT_EVENTS_CAP + 1)
    ]
    state = fold_events(events, pricing)
    assert len(state.recent_events) == RECENT_EVENTS_CAP
    # The oldest one (seconds=0) is evicted; the most recent (seconds=CAP) remains.
    assert all(ev.timestamp != _ts(0) for ev in state.recent_events)
    assert state.recent_events[-1].timestamp == _ts(RECENT_EVENTS_CAP)


# qa F9 — unknown kind no-op (forward-compat).
def test_unknown_event_kind_is_noop(pricing: PricingTable) -> None:
    weird = LiveEvent(kind="future_kind", timestamp=_ts(0), lane_id="main")
    state = apply_event(empty_state(), weird, pricing)
    assert state == empty_state()


# qa F10 — mark_orphans triplet.
def test_mark_orphans_noop_when_no_agents() -> None:
    state = empty_state()
    assert mark_orphans(state) is state  # identity, not just equality


def test_mark_orphans_noop_when_all_complete(pricing: PricingTable) -> None:
    state = fold_events(
        [_dispatch_event(0, "tool_x", "qa"), _result_event(1, "tool_x")],
        pricing,
    )
    out = mark_orphans(state)
    assert out is state  # the no-change fast path returns the same object


def test_mark_orphans_only_active_lanes_transition(pricing: PricingTable) -> None:
    state = fold_events(
        [
            _dispatch_event(0, "tool_done", "qa"),
            _result_event(1, "tool_done"),
            _dispatch_event(2, "tool_hung", "security"),  # never resulted -> still active
        ],
        pricing,
    )
    out = mark_orphans(state)
    by_id = {a.lane_id: a for a in out.agents}
    assert by_id["tool_done"].status == LANE_COMPLETE
    assert by_id["tool_hung"].status == LANE_ORPHANED


# qa F11 — ordering: message-before-dispatch creates the lane.
def test_message_before_dispatch_then_dispatch_is_idempotent(pricing: PricingTable) -> None:
    state = fold_events(
        [
            _msg_event(0, "tool_x", "claude-sonnet-4-6", input_tokens=100, output_tokens=50),
            _dispatch_event(1, "tool_x", "qa"),  # late dispatch
        ],
        pricing,
    )
    assert len(state.agents) == 1
    # Tokens accumulated on the implicitly-created lane stay intact.
    assert state.agents[0].input_tokens == 100
    assert state.agents[0].output_tokens == 50


def test_subagent_message_creates_lane_with_carried_agent_type(pricing: PricingTable) -> None:
    # If the dispatch carried an agent_type and a later message did not,
    # the type carried on the lane is preserved.
    state = fold_events(
        [
            _dispatch_event(0, "tool_x", "security-specialist"),
            _msg_event(1, "tool_x", "claude-sonnet-4-6", input_tokens=100, output_tokens=50),
        ],
        pricing,
    )
    assert state.agents[0].agent_type == "security-specialist"


# qa F12 — purity seam (AC14): no scripts.* or transcript IO in live.py's import graph.
@pytest.mark.regression
def test_live_module_import_graph_is_pure() -> None:
    # Regression (R14/AC14): src/telemetry/live.py must import nothing from
    # scripts.* and nothing that pulls a transcript-IO module. The transport
    # layer (scripts/telemetry/dashboard_server.py) is the seam — the live
    # fold model is pure and unit-testable in isolation. A future edit that
    # accidentally imports `scripts.ingest_token_usage` for "convenience" must
    # fail this guard.
    import importlib
    import sys

    # Force a clean re-import so we count exactly what live.py itself drags in.
    for name in list(sys.modules):
        if name == "src.telemetry.live":
            del sys.modules[name]
    before = set(sys.modules)
    importlib.import_module("src.telemetry.live")
    pulled = set(sys.modules) - before
    forbidden_prefixes = ("scripts",)
    forbidden_names = {"transcript", "transcript_io", "ingest_token_usage"}
    offenders = [
        name
        for name in pulled
        if any(name.startswith(p + ".") or name == p for p in forbidden_prefixes)
        or name in forbidden_names
    ]
    assert offenders == [], (
        f"live.py import graph leaked transport / transcript-IO modules: {offenders}"
    )
