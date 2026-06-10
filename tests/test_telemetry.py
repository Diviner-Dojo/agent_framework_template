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
    _render_agent_lane_row,
    _render_agent_lanes_panel,
    _render_live_stream_panel,
    _render_per_turn_cost_chart_panel,
    _render_runway_estimate,
    _render_runway_panel,
    render_console_summary,
    render_dashboard_html,
    render_live_fragment,
    render_live_shell_html,
)
from src.telemetry.drift import (
    DRIFT_KINDS,
    STALE_PRICING,
    STALE_SUBSCRIPTION_FEE,
    UNKNOWN_MODEL,
    ConfigDriftSignal,
    detect_config_drift,
    detect_stale_pricing_drift,
    detect_stale_subscription_drift,
    detect_unknown_model_drift,
)
from src.telemetry.drift import REMEDIATION_HINTS as DRIFT_REMEDIATION_HINTS
from src.telemetry.failures import (
    CONFIG,
    ERROR_CLASSES,
    MAX_RETRY_CHAIN_GAP_SECONDS,
    NETWORK,
    NOT_FOUND,
    ORPHAN,
    ORPHANED_SUBAGENT,
    OTHER,
    PERMISSION,
    REMEDIATION_HINTS,
    RETRY_LOOP,
    TIMEOUT,
    VALIDATION,
    FailureSignal,
    RankedFailure,
    SubagentDispatch,
    SubagentRun,
    ToolCall,
    classify_error,
    detect_orphaned_subagents,
    detect_retry_loops,
    group_retry_chains,
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
    AgentLane,
    LiveCostEvent,
    LiveEvent,
    LiveState,
    RunwayGauge,
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
    # ux FRICTION-6 fold (REV-20260607-200447): the default OTel link label
    # spells out "OpenTelemetry" and announces the new-tab behaviour so the
    # gatekeeper knows the context shift before clicking.
    assert "enable OpenTelemetry (opens in new tab)" in html


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


# --- error-class classifier + remediation hints (Phase 3 Unit 1) ----------- #


def _sig(failure_type: str, signature: str) -> FailureSignal:
    """Build a minimal FailureSignal for classifier tests."""
    return FailureSignal(
        failure_type=failure_type,
        signature=signature,
        occurrence_count=1,
        tier="opus",
        wasted_tokens_out=10,
    )


def test_classify_orphaned_subagent_returns_orphan_class() -> None:
    # The structural mapping: an orphaned_subagent failure_type is exactly the
    # spec's "orphan" class — never anything else.
    s = _sig(ORPHANED_SUBAGENT, "toolu_123")
    assert classify_error(s) == ORPHAN


@pytest.mark.parametrize("tool", ["Read", "Glob", "Grep", "LS"])
def test_classify_read_style_retry_loop_returns_not_found(tool: str) -> None:
    # A retry loop on a read-style tool (file/symbol lookup) is the
    # not_found heuristic: the dominant cause is a path/pattern that doesn't
    # exist.
    s = _sig(RETRY_LOOP, f"{tool}:abc123")
    assert classify_error(s) == NOT_FOUND


@pytest.mark.parametrize("tool", ["Edit", "Write", "NotebookEdit"])
def test_classify_edit_style_retry_loop_returns_validation(tool: str) -> None:
    # A retry loop on an edit-style tool (Edit/Write/NotebookEdit) is the
    # validation heuristic: old_string mismatch / payload rejected.
    s = _sig(RETRY_LOOP, f"{tool}:abc123")
    assert classify_error(s) == VALIDATION


@pytest.mark.regression
def test_classify_bash_retry_loop_returns_other_not_a_guess() -> None:
    # ADR-0020 honesty: Bash retry causes are genuinely ambiguous (permission,
    # network, timeout, missing command, …). The classifier MUST NOT guess one;
    # it returns the honest "other" class.
    assert classify_error(_sig(RETRY_LOOP, "Bash:abc123")) == OTHER


@pytest.mark.regression
def test_classify_unknown_tool_retry_loop_returns_other() -> None:
    # An unknown tool name falls into "other" — the classifier never
    # fabricates a class to make the panel look tidier.
    assert classify_error(_sig(RETRY_LOOP, "SomeNewTool:abc")) == OTHER


@pytest.mark.regression
def test_classify_unknown_failure_type_returns_other() -> None:
    # A failure_type the classifier doesn't recognise is honestly "other",
    # not a silently-fabricated mapping.
    assert classify_error(_sig("future_failure_type", "anything")) == OTHER


def test_classify_handles_signature_with_colon_in_hash() -> None:
    # The signature is "<tool>:<input_hash>"; the split is on the FIRST colon
    # so a hash containing ":" doesn't corrupt the tool-name read.
    assert classify_error(_sig(RETRY_LOOP, "Read:abc:def:123")) == NOT_FOUND


def test_remediation_hint_exists_for_every_error_class() -> None:
    # Each canonical class MUST have a static hint — the panel renderer reads
    # this dict with REMEDIATION_HINTS[cls] (no .get fallback) so a missing
    # key would crash the render path.
    for cls in ERROR_CLASSES:
        assert cls in REMEDIATION_HINTS
        assert REMEDIATION_HINTS[cls].strip(), f"hint for {cls} is empty"


@pytest.mark.regression
def test_remediation_hints_keys_match_error_classes_exactly() -> None:
    # Symmetric drift guard (arch F1 fold REV-20260609-052616): an orphan key
    # in REMEDIATION_HINTS (a hint for a class that was removed from
    # ERROR_CLASSES) is just as much a programmer error as a missing hint.
    # Pin both directions with a single set-equality assertion so the
    # taxonomy + hint dict cannot drift apart silently.
    assert set(REMEDIATION_HINTS) == set(ERROR_CLASSES)


def test_error_classes_contains_seven_spec_classes_plus_other() -> None:
    # The spec names 7 classes; "other" is the honest-absence default. Pinning
    # the set guards against a stealth rename or accidental removal.
    assert set(ERROR_CLASSES) == {
        NOT_FOUND,
        PERMISSION,
        ORPHAN,
        CONFIG,
        VALIDATION,
        TIMEOUT,
        NETWORK,
        OTHER,
    }


# --- failures panel grouping (Phase 3 Unit 1) ------------------------------ #


def _ranked(
    failure_type: str, signature: str, *, cost: float | None, tokens: int
) -> RankedFailure:
    """Build a RankedFailure with chosen cost + wasted tokens for panel tests."""
    sig = FailureSignal(
        failure_type=failure_type,
        signature=signature,
        occurrence_count=3,
        tier="opus" if cost is not None else UNKNOWN_TIER,
        wasted_tokens_out=tokens,
        detail=f"{signature.split(':', 1)[0]} called identically",
    )
    return RankedFailure(signal=sig, cost_usd=cost)


def test_failures_panel_groups_by_class_with_hint_header() -> None:
    # Two failures of different classes -> two class groups in the rendered
    # HTML, each carrying its class label + static hint. The hint text is
    # html.escape-d, so we assert on a substring that contains no
    # quote/apostrophe characters (avoiding entity-form drift in the test).
    rfs = [
        _ranked(ORPHANED_SUBAGENT, "toolu_1", cost=5.0, tokens=100),
        _ranked(RETRY_LOOP, "Read:abc", cost=1.0, tokens=50),
    ]
    html_doc = render_dashboard_html(_data(failures=rfs))
    assert 'data-class="orphan"' in html_doc
    assert 'data-class="not_found"' in html_doc
    assert "Orphan" in html_doc  # class label rendered
    assert "Not found" in html_doc
    # Use a quote-free substring of each hint so the assertion survives the
    # html.escape pass on apostrophes/quotes.
    assert "A subagent was dispatched but never finished" in html_doc
    assert "the agent was looking for a file" in html_doc


@pytest.mark.regression
def test_failures_panel_other_group_rendered_honestly_not_omitted() -> None:
    # ADR-0020 honesty: an unclassifiable signal must render in an explicit
    # "other" group with the "does not fit a known class" hint, NEVER omitted
    # or silently folded into a real class.
    rfs = [_ranked(RETRY_LOOP, "Bash:abc", cost=1.0, tokens=10)]
    html_doc = render_dashboard_html(_data(failures=rfs))
    assert 'data-class="other"' in html_doc
    # Substring without quote/apostrophe so it survives html.escape on the hint.
    assert "These signals do not fit a known class" in html_doc


def test_failures_panel_group_order_priced_before_unpriced() -> None:
    # Mirrors rank_failures: priced groups come before unpriced groups so an
    # unpriced waste cannot preempt a real measured cost in the visual order.
    rfs = [
        _ranked(RETRY_LOOP, "Read:abc", cost=None, tokens=1_000_000),  # not_found, unpriced
        _ranked(ORPHANED_SUBAGENT, "toolu_1", cost=0.0001, tokens=5),  # orphan, priced
    ]
    html_doc = render_dashboard_html(_data(failures=rfs))
    assert html_doc.index('data-class="orphan"') < html_doc.index('data-class="not_found"')


@pytest.mark.regression
def test_failures_panel_mixed_priced_group_outranks_pure_unpriced_group() -> None:
    # qa F1 fold REV-20260609-052616: a MIXED group (at least one priced +
    # at least one unpriced signal) must still rank before a pure-unpriced
    # group, even if the unpriced group has a much larger token total. This
    # guards the ``has_priced = any(...)`` semantic in _group_failures_by_class
    # against a future "simplification" to ``all(...)`` that would silently
    # demote mixed groups behind huge pure-unpriced waste.
    rfs = [
        # not_found bucket: one priced (small cost) + one unpriced (small tokens).
        _ranked(RETRY_LOOP, "Read:hit", cost=0.001, tokens=5),
        _ranked(RETRY_LOOP, "Read:miss", cost=None, tokens=5),
        # orphan bucket: pure-unpriced with enormous wasted tokens.
        _ranked(ORPHANED_SUBAGENT, "toolu_1", cost=None, tokens=10_000_000),
    ]
    html_doc = render_dashboard_html(_data(failures=rfs))
    # The mixed not_found group must appear before the pure-unpriced orphan
    # group even though orphan's token waste is several orders of magnitude
    # larger.
    assert html_doc.index('data-class="not_found"') < html_doc.index('data-class="orphan"')


def test_failures_panel_preserves_ranked_order_within_group() -> None:
    # Two failures in the SAME class — their inbound ranked order must be
    # preserved verbatim inside the group's <tbody>.
    rfs = [
        _ranked(RETRY_LOOP, "Read:high", cost=10.0, tokens=100),
        _ranked(RETRY_LOOP, "Read:low", cost=0.1, tokens=10),
    ]
    html_doc = render_dashboard_html(_data(failures=rfs))
    assert html_doc.index("Read:high") < html_doc.index("Read:low")


@pytest.mark.regression
def test_failures_panel_class_label_and_hint_are_escaped() -> None:
    # Defense in depth: class label + hint pass through _esc, so even if a
    # future class name carried HTML it could not inject. Today's class names
    # are static so the assertion runs against the static content.
    rfs = [_ranked(RETRY_LOOP, "Bash:abc", cost=1.0, tokens=10)]
    html_doc = render_dashboard_html(_data(failures=rfs))
    # No raw <script> markup; hint is escaped text only.
    assert "<script>" not in html_doc
    # Hint is rendered as plain text inside <p class="hint">.
    assert '<p class="hint">' in html_doc


# --- retry-chain nesting (Phase 3 Unit 3 — SPEC-20260610-001134) ---------- #


_BASE_TS = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)


def _chain_signal(
    tool: str,
    suffix: str,
    *,
    offset_seconds: float,
    duration_seconds: float = 0.0,
    failure_type: str = RETRY_LOOP,
    tokens: int = 10,
) -> FailureSignal:
    """Build a FailureSignal with deterministic tz-aware timestamps.

    ``offset_seconds`` is the seconds offset from ``_BASE_TS`` for ``first_seen``;
    ``duration_seconds`` is the time between ``first_seen`` and ``last_seen``
    (0 = zero-duration / instantaneous signal). Tokens default low so the
    chain-total assertions don't drift on cost arithmetic.
    """
    first = _BASE_TS + timedelta(seconds=offset_seconds)
    last = first + timedelta(seconds=duration_seconds)
    return FailureSignal(
        failure_type=failure_type,
        signature=f"{tool}:{suffix}",
        occurrence_count=3,
        tier="opus",
        wasted_tokens_out=tokens,
        detail=f"{tool} called identically",
        first_seen=first,
        last_seen=last,
    )


def _chain_rf(
    tool: str,
    suffix: str,
    *,
    offset_seconds: float,
    duration_seconds: float = 0.0,
    failure_type: str = RETRY_LOOP,
    tokens: int = 10,
    cost: float | None = 0.001,
) -> RankedFailure:
    """Build a RankedFailure with a tz-aware FailureSignal (chain test helper)."""
    return RankedFailure(
        signal=_chain_signal(
            tool,
            suffix,
            offset_seconds=offset_seconds,
            duration_seconds=duration_seconds,
            failure_type=failure_type,
            tokens=tokens,
        ),
        cost_usd=cost,
    )


def test_group_retry_chains_empty_input_returns_empty() -> None:
    # Spec A1 — empty input is a chain of nothing.
    assert group_retry_chains([]) == []


def test_group_retry_chains_two_retries_inside_window_chain_to_length_two() -> None:
    # Spec A2 — gap strictly less than window chains.
    rfs = [
        _chain_rf("Read", "a", offset_seconds=0),
        _chain_rf("Read", "b", offset_seconds=60),  # gap=60s, window=120s
    ]
    chains = group_retry_chains(rfs)
    assert len(chains) == 1
    assert chains[0].size() == 2
    assert chains[0].head is rfs[0]
    assert chains[0].links == (rfs[1],)


@pytest.mark.regression
def test_group_retry_chains_boundary_inclusive_at_max_gap_seconds() -> None:
    # Spec A2 + qa F2 fold — gap == MAX_RETRY_CHAIN_GAP_SECONDS chains
    # (boundary inclusive; the `<=` in _retry_pair_chains).
    rfs = [
        _chain_rf("Read", "a", offset_seconds=0),
        _chain_rf("Read", "b", offset_seconds=float(MAX_RETRY_CHAIN_GAP_SECONDS)),
    ]
    chains = group_retry_chains(rfs)
    assert len(chains) == 1
    assert chains[0].size() == 2


@pytest.mark.regression
def test_group_retry_chains_one_second_past_window_does_not_chain() -> None:
    # Spec A3 — gap == window + 1 does NOT chain (off-by-one guard).
    rfs = [
        _chain_rf("Read", "a", offset_seconds=0),
        _chain_rf("Read", "b", offset_seconds=float(MAX_RETRY_CHAIN_GAP_SECONDS + 1)),
    ]
    chains = group_retry_chains(rfs)
    assert len(chains) == 2
    assert all(chain.size() == 1 for chain in chains)


def test_group_retry_chains_orphan_adjacent_to_retry_does_not_chain() -> None:
    # Spec A4 — an orphan signal cannot chain with a retry (both endpoints
    # must be RETRY_LOOP).
    rfs = [
        _chain_rf("Read", "a", offset_seconds=0),
        _chain_rf("_", "orphan_id", offset_seconds=30, failure_type=ORPHANED_SUBAGENT),
    ]
    chains = group_retry_chains(rfs)
    # Only the retry is wrapped as a chain (length 1); the orphan is dropped
    # from the chain layer (rendered separately by the row helper).
    assert len(chains) == 1
    assert chains[0].size() == 1
    assert chains[0].head.signal.failure_type == RETRY_LOOP


@pytest.mark.regression
def test_group_retry_chains_interleaved_orphan_does_not_break_chain() -> None:
    # Spec A4b (qa F1 fold) — a non-retry signal interleaved in time between
    # two retries (retry@0s, orphan@60s, retry@80s) MUST NOT prevent the two
    # retries from chaining. The orphan is skipped over, not chain-reset.
    rfs = [
        _chain_rf("Read", "a", offset_seconds=0),
        _chain_rf("_", "orphan_id", offset_seconds=60, failure_type=ORPHANED_SUBAGENT),
        _chain_rf("Read", "b", offset_seconds=80),  # gap from retry-a's last_seen=0s -> 80s
    ]
    chains = group_retry_chains(rfs)
    assert len(chains) == 1
    assert chains[0].size() == 2
    assert chains[0].head.signal.signature == "Read:a"
    assert chains[0].links[0].signal.signature == "Read:b"


def test_group_retry_chains_missing_first_seen_never_chains() -> None:
    # Spec A5 — first_seen=None on the next signal blocks chaining.
    first = _chain_rf("Read", "a", offset_seconds=0)
    second_sig = FailureSignal(
        failure_type=RETRY_LOOP,
        signature="Read:b",
        occurrence_count=3,
        tier="opus",
        wasted_tokens_out=10,
        detail="Read called identically",
        first_seen=None,  # <-- missing
        last_seen=_BASE_TS + timedelta(seconds=60),
    )
    rfs = [first, RankedFailure(signal=second_sig, cost_usd=0.001)]
    chains = group_retry_chains(rfs)
    assert len(chains) == 2  # two length-1 chains, never merged


def test_group_retry_chains_missing_last_seen_never_chains() -> None:
    # Spec A5 — last_seen=None on the prev signal blocks chaining.
    first_sig = FailureSignal(
        failure_type=RETRY_LOOP,
        signature="Read:a",
        occurrence_count=3,
        tier="opus",
        wasted_tokens_out=10,
        detail="Read called identically",
        first_seen=_BASE_TS,
        last_seen=None,  # <-- missing
    )
    first = RankedFailure(signal=first_sig, cost_usd=0.001)
    second = _chain_rf("Read", "b", offset_seconds=60)
    chains = group_retry_chains([first, second])
    assert len(chains) == 2  # two length-1 chains


@pytest.mark.regression
def test_group_retry_chains_tz_mismatch_caught_as_unchainable() -> None:
    # Spec A5b (qa F3 fold) — one tz-aware + one tz-naive timestamp would
    # raise TypeError on subtraction; the function catches it and treats the
    # pair as unchainable rather than crashing the render path.
    tz_aware = _chain_rf("Read", "a", offset_seconds=0)
    naive_sig = FailureSignal(
        failure_type=RETRY_LOOP,
        signature="Read:b",
        occurrence_count=3,
        tier="opus",
        wasted_tokens_out=10,
        detail="Read called identically",
        first_seen=datetime(2026, 6, 10, 12, 1, 0),  # <-- tz-naive
        last_seen=datetime(2026, 6, 10, 12, 1, 0),
    )
    naive = RankedFailure(signal=naive_sig, cost_usd=0.001)
    chains = group_retry_chains([tz_aware, naive])
    # No crash, two length-1 chains.
    assert len(chains) == 2
    assert all(chain.size() == 1 for chain in chains)


def test_retry_chain_total_cost_none_when_all_links_unpriced() -> None:
    # Spec A6 — every link cost_usd is None -> total is None (honest absence).
    rfs = [
        _chain_rf("Read", "a", offset_seconds=0, cost=None),
        _chain_rf("Read", "b", offset_seconds=60, cost=None),
    ]
    chains = group_retry_chains(rfs)
    assert chains[0].total_cost_usd is None


def test_retry_chain_total_cost_sums_priced_only_in_mixed_chain() -> None:
    # Spec A6a — a single priced link in a mixed chain contributes; unpriced
    # links are excluded (never fabricated as 0).
    rfs = [
        _chain_rf("Read", "a", offset_seconds=0, cost=0.5),
        _chain_rf("Read", "b", offset_seconds=60, cost=None),
    ]
    chains = group_retry_chains(rfs)
    assert chains[0].total_cost_usd == 0.5


@pytest.mark.regression
def test_retry_chain_total_cost_treats_zero_as_priced_not_falsy() -> None:
    # Spec A6b (qa F6 fold) — a link with cost_usd == 0.0 IS priced
    # (genuinely free) and contributes 0.0 to the sum. Guards against a
    # future `if cost_usd:` truthy guard accidentally excluding 0-cost rows.
    rfs = [
        _chain_rf("Read", "a", offset_seconds=0, cost=0.0),
        _chain_rf("Read", "b", offset_seconds=60, cost=0.25),
    ]
    chains = group_retry_chains(rfs)
    assert chains[0].total_cost_usd == 0.25  # 0.0 + 0.25, NOT None


def test_retry_chain_total_wasted_tokens_sums_every_link() -> None:
    # Spec A7 — wasted-token total is the sum across every link.
    rfs = [
        _chain_rf("Read", "a", offset_seconds=0, tokens=100),
        _chain_rf("Read", "b", offset_seconds=60, tokens=50),
    ]
    chains = group_retry_chains(rfs)
    assert chains[0].total_wasted_tokens == 150


@pytest.mark.regression
def test_retry_chain_zero_duration_signals_with_zero_gap_chain() -> None:
    # Spec A7b (qa F5 fold) — two signals with first_seen == last_seen
    # (instantaneous) separated by 0s gap chain (0 <= window).
    rfs = [
        _chain_rf("Read", "a", offset_seconds=0, duration_seconds=0),
        _chain_rf("Read", "b", offset_seconds=0, duration_seconds=0),
    ]
    chains = group_retry_chains(rfs)
    assert len(chains) == 1
    assert chains[0].size() == 2


@pytest.mark.regression
def test_length_one_chain_renders_no_chain_scaffold() -> None:
    # Spec A8 (qa F4 fold) — STRUCTURAL ABSENCE: a length-1 chain emits no
    # data-chain-size attribute, no retry-chain-link rows, no aria-label
    # on the parent row. Property assertions (not byte equality) so a
    # whitespace/attribute-order refactor of the surrounding HTML does not
    # break the regression guard.
    rfs = [_ranked(RETRY_LOOP, "Read:lone", cost=0.001, tokens=10)]
    html_doc = render_dashboard_html(_data(failures=rfs))
    assert "data-chain-size" not in html_doc
    # Match the HTML class attribute, not the inline CSS selector (the
    # stylesheet's .retry-chain-link rule contains the substring).
    assert 'class="retry-chain-link"' not in html_doc
    assert 'aria-label="Retry chain' not in html_doc


def test_chain_of_two_renders_parent_attributes_and_one_link_row() -> None:
    # Spec A9 — data-chain-size, aria-label, and exactly N-1 retry-chain-link
    # child rows (here N=2 -> 1 link row).
    rfs = [
        _chain_rf("Read", "a", offset_seconds=0),
        _chain_rf("Read", "b", offset_seconds=60),
    ]
    html_doc = render_dashboard_html(_data(failures=rfs))
    assert 'data-chain-size="2"' in html_doc
    assert 'aria-label="Retry chain (2 consecutive retries)"' in html_doc
    assert html_doc.count('class="retry-chain-link"') == 1


def test_chain_of_three_renders_two_link_rows_in_temporal_order() -> None:
    # Spec A9 + A10 — N=3 chain emits 2 link rows; links in temporal order
    # (first_seen ascending). The head's first_seen is the earliest.
    rfs = [
        _chain_rf("Read", "first", offset_seconds=0),
        _chain_rf("Read", "second", offset_seconds=30),
        _chain_rf("Read", "third", offset_seconds=80),
    ]
    html_doc = render_dashboard_html(_data(failures=rfs))
    assert 'data-chain-size="3"' in html_doc
    assert html_doc.count('class="retry-chain-link"') == 2
    # Temporal order: head's signature comes first, then second, then third.
    assert html_doc.index("Read:first") < html_doc.index("Read:second")
    assert html_doc.index("Read:second") < html_doc.index("Read:third")


@pytest.mark.regression
def test_chain_link_row_carries_non_color_glyph_for_wcag_1_4_1() -> None:
    # Spec R5 + ux F1 T2-checkpoint fold — link rows carry a non-color
    # structural cue (the U+21B3 "↳" glyph wrapped in aria-hidden="true"
    # so screen readers don't double-announce it). Guards against a future
    # CSS-only indent refactor that removes the glyph and silently fails
    # WCAG 1.4.1 (distinction not by color alone).
    rfs = [
        _chain_rf("Read", "a", offset_seconds=0),
        _chain_rf("Read", "b", offset_seconds=60),
    ]
    html_doc = render_dashboard_html(_data(failures=rfs))
    # The glyph is encoded as the HTML entity &#x21B3; in the rendered output.
    assert "&#x21B3;" in html_doc
    assert 'class="chain-glyph"' in html_doc
    assert 'aria-hidden="true"' in html_doc


@pytest.mark.regression
def test_group_retry_chains_is_deterministic_across_repeated_calls() -> None:
    # Spec A10b (qa F8 fold) — calling the pure fold twice on the same input
    # produces identical output. Guards against any future non-stable sort
    # introduction.
    rfs = [
        _chain_rf("Read", "a", offset_seconds=0),
        _chain_rf("Read", "b", offset_seconds=60),
        _chain_rf("Read", "c", offset_seconds=500),  # outside window -> new chain
        _chain_rf("Read", "d", offset_seconds=540),
    ]
    first = group_retry_chains(rfs)
    second = group_retry_chains(rfs)
    assert first == second
    # Sanity: the second pair-out-of-window split produced 2 chains.
    assert len(first) == 2
    assert first[0].size() == 2
    assert first[1].size() == 2


def test_max_retry_chain_gap_seconds_override_changes_boundary() -> None:
    # Spec A11 — passing max_gap_seconds=60 (instead of the 120 default)
    # narrows the window; a 90s gap chains under the default but not the
    # override.
    rfs = [
        _chain_rf("Read", "a", offset_seconds=0),
        _chain_rf("Read", "b", offset_seconds=90),
    ]
    chains_default = group_retry_chains(rfs)
    chains_narrow = group_retry_chains(rfs, max_gap_seconds=60)
    assert len(chains_default) == 1
    assert chains_default[0].size() == 2
    assert len(chains_narrow) == 2
    assert all(chain.size() == 1 for chain in chains_narrow)


@pytest.mark.regression
def test_group_retry_chains_all_orphan_input_returns_empty() -> None:
    # Spec A11b (qa F7 fold) — all-non-retry input yields no chains
    # (orphans are never wrapped in a RetryChain; they pass through to the
    # row renderer untouched).
    rfs = [
        _chain_rf("_", "o1", offset_seconds=0, failure_type=ORPHANED_SUBAGENT),
        _chain_rf("_", "o2", offset_seconds=30, failure_type=ORPHANED_SUBAGENT),
    ]
    assert group_retry_chains(rfs) == []


def test_failures_panel_renders_orphan_alongside_retry_chain_in_same_class_group() -> None:
    # End-to-end: a single class group with one orphan + one retry-loop
    # renders both (orphan via the flat row path; retry-loop via the chain
    # of length 1). Confirms _render_failure_class_group composes the two
    # paths cleanly.
    rfs = [
        # orphan goes to ORPHAN class, retry to OTHER (Bash) — render both
        # so the panel proves it composes; ordering is by class rank.
        _ranked(ORPHANED_SUBAGENT, "orphan_id", cost=2.0, tokens=200),
        _ranked(RETRY_LOOP, "Bash:abc", cost=0.001, tokens=10),
    ]
    html_doc = render_dashboard_html(_data(failures=rfs))
    # Both signatures appear; neither chain scaffold appears (both length-1
    # in their own class groups).
    assert "orphan_id" in html_doc
    assert "Bash:abc" in html_doc
    assert "data-chain-size" not in html_doc


# --- /review (REV-20260610-003237) in-session fold tests ------------------ #


@pytest.mark.regression
def test_failures_panel_class_group_with_chain_and_standalone_retry_composes() -> None:
    # qa F1 fold REV-20260610-003237: a class group containing BOTH a
    # length-≥2 chain AND a separate standalone retry exercises the
    # chain_iter / next_chain double-advancement logic in
    # _render_failure_class_group. The arch F1 fold (identity-based skip
    # lookup) also rides this case — a future regression that broke
    # iterator advancement or skip identity would render the standalone
    # row twice or drop it.
    rfs = [
        # Two Read retries within window -> chain of 2 in NOT_FOUND class
        _chain_rf("Read", "cascade-1", offset_seconds=0),
        _chain_rf("Read", "cascade-2", offset_seconds=60),
        # Isolated Read retry well outside window -> standalone in same class
        _chain_rf("Read", "isolated", offset_seconds=10_000),
    ]
    html_doc = render_dashboard_html(_data(failures=rfs))
    # Chain rendered exactly once
    assert html_doc.count('data-chain-size="2"') == 1
    assert html_doc.count('class="retry-chain-link"') == 1
    # Standalone signature appears as a flat row (no chain scaffold around it)
    assert "Read:isolated" in html_doc
    # Standalone is rendered after the chain block (rank-order preserved)
    chain_pos = html_doc.index('data-chain-size="2"')
    standalone_pos = html_doc.index("Read:isolated")
    assert chain_pos < standalone_pos


@pytest.mark.regression
def test_chain_link_row_fields_are_escaped() -> None:
    # qa F3 fold REV-20260610-003237: the length-≥2 chain link-row
    # interpolation seam (sl.detail, sl.signature) is a NEW render path —
    # the pre-Phase-3-Unit-3 escape tests only exercised the flat-row /
    # length-1 path. Build a chain whose LINK carries _XSS in both detail
    # and signature and assert the escape contract holds end-to-end.
    head = _chain_rf("Read", "ok", offset_seconds=0)
    link_sig = FailureSignal(
        failure_type=RETRY_LOOP,
        signature=f"Read:{_XSS}",
        occurrence_count=3,
        tier="opus",
        wasted_tokens_out=10,
        detail=_XSS,
        first_seen=_BASE_TS + timedelta(seconds=60),
        last_seen=_BASE_TS + timedelta(seconds=60),
    )
    link = RankedFailure(signal=link_sig, cost_usd=0.001)
    html_doc = render_dashboard_html(_data(failures=[head, link]))
    # Both flat- and chain-link rendering must escape; _XSS must NOT leak raw
    assert _XSS not in html_doc
    # Confirm the chain DID render (so we know the escape ran on the link path)
    assert 'data-chain-size="2"' in html_doc
    assert 'class="retry-chain-link"' in html_doc
    # Escaped form is present
    assert "&lt;script&gt;" in html_doc


@pytest.mark.regression
def test_group_retry_chains_overlapping_signals_chain() -> None:
    # qa F2 fold REV-20260610-003237: a "next.first_seen < prev.last_seen"
    # case (negative gap) — the boundary check `gap_seconds <= 120` admits
    # negative gaps, which is correct (overlapping retries should chain).
    # Pin the implicit "overlapping is fine" decision so a future tightening
    # to `0 <= gap_seconds <= 120` is caught.
    rfs = [
        _chain_rf("Read", "a", offset_seconds=0, duration_seconds=120),
        # next.first_seen=60 < prev.last_seen=120 -> gap_seconds = -60
        _chain_rf("Read", "b", offset_seconds=60),
    ]
    chains = group_retry_chains(rfs)
    assert len(chains) == 1
    assert chains[0].size() == 2


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
    # Phase 3 Unit 2 added a Config-drift summary line (always present in one
    # of 3 states), so the per-state line range is bumped from 5-6 to 6-7.
    assert 6 <= len(lines) <= 7


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


# --- Phase 4 Unit 4.3: summary-only renderer mode (output_path=None) -------- #


def test_console_summary_without_output_path_omits_dashboard_line() -> None:
    """``output_path=None`` (CLI inline summary) must not print a Dashboard line.

    Summary-only mode produces no HTML artifact, so a ``Dashboard: <path>``
    line would reference a file that does not exist (ADR-0020 honesty).
    The digest is exactly one line shorter than the with-artifact variant.
    """
    with_path = render_console_summary(_data(), output_path="C:/tmp/telemetry_dashboard.html")
    without = render_console_summary(_data(), output_path=None)
    assert not any(line.startswith("Dashboard:") for line in without)
    # Identical digest body; only the Dashboard line is dropped (the trailing
    # absence advisory differs by intent — its copy is artifact-aware).
    body = [ln for ln in without if not ln.startswith("Note:")]
    body_with_path = [ln for ln in with_path[1:] if not ln.startswith("Note:")]
    assert body == body_with_path
    # qa F2: the len arithmetic relies on _data() defaults always producing the
    # Note line (pricing_check + config_drift default to absence states); the
    # body comparison above catches any asymmetry if that fixture ever changes.
    assert len(without) == len(with_path) - 1
    text = "\n".join(without)
    text.encode("ascii")  # C7 discipline carries into summary-only mode
    text.encode("cp1252")


def test_console_summary_summary_only_absence_note_never_references_the_page() -> None:
    """The trailing absence advisory must not say "see the page" when no page exists."""
    lines = render_console_summary(
        _data(cost_state=STATE_NOT_RUN, failures_state=STATE_NOT_RUN), output_path=None
    )
    notes = [line for line in lines if line.startswith("Note:")]
    assert notes, "absence states present, so the advisory line must render"
    assert "see the page" not in notes[0]
    assert "launch the dashboard for detail" in notes[0]


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


@pytest.mark.regression
def test_subagent_lane_with_unknown_tier_model_is_uncosted(pricing: PricingTable) -> None:
    # qa F3 (subagent variant): the uncosted-turn path must also fire on the
    # non-main branch — a future model family that lands before pricing.yaml is
    # updated could arrive on a subagent before it ever shows up on the main lane.
    #
    # qa F1 fold from REV-20260608-034041 (arch F1 fold review): also assert the
    # PER-EVENT `uncosted` flag on `recent_events` for the non-main branch.
    # `_apply_message` forks on `lane_id == "main"` vs the else branch; both reach
    # the same unified `LiveCostEvent(...)` constructor call today (so per-event
    # propagation is symmetric), but a future refactor that split the constructor
    # call into the two branches could break the subagent path without triggering
    # the main-lane-only tests in the arch F1 regression cohort. This guard mirrors
    # the main-lane assertion in `test_apply_message_per_event_uncosted_flag_priced_vs_uncosted`.
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
    # qa F1 fold (REV-20260608-034041): per-event uncosted flag on the non-main branch.
    assert len(state.recent_events) == 1
    assert state.recent_events[-1].lane_id == "tool_x"
    assert state.recent_events[-1].uncosted is True


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


# arch F1 fold (REV-20260608-025749) — per-event uncosted flag on LiveCostEvent.
@pytest.mark.regression
def test_apply_message_per_event_uncosted_flag_priced_vs_uncosted(
    pricing: PricingTable,
) -> None:
    """``LiveCostEvent.uncosted`` distinguishes a priced cheap turn from an unpriced tier.

    Arch F1 from REV-20260608-025749: before this fold the chart payload
    collapsed a priced $0 (a turn with truly tiny token counts) with an
    uncosted turn (an unknown-tier turn forced to ``cost_usd=0.0``). At the
    ``LiveState.uncosted_turns`` aggregate level the distinction was always
    there, but per-event consumers (the chart panel's data block) had no
    way to read it back. The fold now threads the ``uncosted`` flag through
    ``_apply_message`` onto each emitted ``LiveCostEvent``.

    A regression that dropped the propagation would re-collapse the two
    cases on the chart — the per-event flag is the single source of truth
    for the visual distinction.
    """
    state = fold_events(
        [
            # Priced opus turn → cost > 0, uncosted=False.
            _msg_event(0, "main", "claude-opus-4-7", input_tokens=1000, output_tokens=500),
            # Unknown tier → cost = 0.0, uncosted=True.
            _msg_event(10, "main", "claude-mystery-9", input_tokens=500, output_tokens=200),
        ],
        pricing,
    )
    assert len(state.recent_events) == 2
    priced, uncosted = state.recent_events
    assert priced.cost_usd == pytest.approx(0.0525)
    assert priced.uncosted is False
    assert uncosted.cost_usd == 0.0
    assert uncosted.uncosted is True
    # Sanity: aggregate state agrees with the per-event flag.
    assert state.uncosted_turns == 1
    assert state.total_cost_usd == pytest.approx(0.0525)


@pytest.mark.regression
def test_live_cost_event_uncosted_defaults_to_false() -> None:
    """``LiveCostEvent`` constructed without the ``uncosted`` kwarg defaults to ``False``.

    A field with a default keeps every existing synthetic construction site
    (the chart panel tests, the live stream panel tests, ad-hoc fixtures)
    valid without modification — a future change that made the field
    required would silently break them.
    """
    ev = LiveCostEvent(
        timestamp=_ts(0),
        lane_id="main",
        kind="turn",
        cost_usd=0.01,
        tokens=100,
    )
    assert ev.uncosted is False


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


# --------------------------------------------------------------------------- #
# Live-render UX tests (REV-20260607-200447 ux FRICTION-1 / 2 / 4)
# --------------------------------------------------------------------------- #
#
# Phase 1 shipped live-panel renderers but no direct render tests (qa F1 in the
# same review). These guards cover the three UX advisories addressed in the
# follow-up commit so a future refactor cannot silently regress them.


@pytest.mark.regression
def test_live_shell_loading_tile_is_distinct_from_absence_tile() -> None:
    """ux FRICTION-1: first-paint placeholder uses ``tile--loading``, NOT ``tile--absent``.

    A transient htmx delay (or a brief 5xx from ``/fragments/live``) must not
    visually present as the honest-absence vocabulary used by ``/fragments/live``
    when the analyzer has not been run — gatekeepers read those two states
    differently. Asserts the loading vocabulary is present and the absence
    vocabulary is NOT used by the placeholder.
    """
    html = render_live_shell_html(generated_label="2026-06-07 23:15 UTC")
    assert 'class="tile tile--loading"' in html
    assert "tile--loading" in html
    # The loading copy is plain-language ("Connecting…"), not "Loading…" which
    # would still be acceptable but is the placeholder the ux review flagged.
    assert "Connecting to live session data" in html
    # Belt-and-braces: the placeholder must not borrow the absence container's
    # class, which would re-introduce the FRICTION-1 confusion.
    placeholder = html.split('id="live-section"', 1)[1].split("</section>", 1)[0]
    assert "tile--absent" not in placeholder
    assert "absence-copy" not in placeholder


@pytest.mark.regression
def test_live_shell_exposes_retrospective_link() -> None:
    """ux FRICTION-4: shell header carries a reachable link to the retrospective view.

    The ``/fragments/retrospective`` route serves a full HTML document (not an
    htmx swap fragment), so a regular ``<a href>`` is the right affordance.
    Without this link the route is live-but-unreachable from the UI.
    """
    html = render_live_shell_html(generated_label="2026-06-07 23:15 UTC")
    assert 'href="/fragments/retrospective"' in html
    assert 'class="nav-link"' in html
    # The link belongs to the shell <nav>, NOT inside the swap target — htmx
    # would otherwise replace it on each poll.
    nav_block = html.split('class="shell-nav"', 1)[1].split("</nav>", 1)[0]
    assert 'href="/fragments/retrospective"' in nav_block
    swap_target = html.split('id="live-section"', 1)[1].split("</section>", 1)[0]
    assert 'href="/fragments/retrospective"' not in swap_target


@pytest.mark.regression
def test_live_fragment_main_lane_renders_primary_badge_and_class(
    pricing: PricingTable,
) -> None:
    """ux FRICTION-2: main session row carries ``lane--primary`` + a ``primary`` badge.

    Differentiates the main lane from dispatched subagent lanes by *position*
    (badge next to the agent label) and *color tint* (a left-border via the
    class). Asserts both, plus that a dispatched-subagent row does NOT get the
    primary treatment (otherwise the differentiation is meaningless).
    """
    state = fold_events(
        [
            # Main session has output, so the runway estimator engages and the
            # row renders normally.
            _msg_event(0, "main", "claude-opus-4-7", input_tokens=200, output_tokens=400),
            _dispatch_event(1, "sub-rowA", agent_type="qa-specialist"),
            _msg_event(2, "sub-rowA", "claude-sonnet-4-6", input_tokens=100, output_tokens=50),
        ],
        pricing,
    )
    html = render_live_fragment(state)
    assert "lane--primary" in html
    assert 'class="lane-badge lane-badge--primary">primary</span>' in html
    # Robust row-isolation: each subagent row is the `<tr>...</tr>` whose first
    # `<td>` carries the lane_id literal (qa F1 in REV-20260607-200447-supplement
    # — splitting on a bare lane-id substring is fragile to future fixtures that
    # repeat the substring elsewhere). We require a `<tr ...><td>sub-rowA</td>`
    # anchor so a coincidental match earlier in the HTML cannot mis-slice.
    anchor = "<td>sub-rowA</td>"
    assert anchor in html
    sub_row_start = html.rindex("<tr ", 0, html.index(anchor))
    sub_row_end = html.index("</tr>", sub_row_start) + len("</tr>")
    sub_row = html[sub_row_start:sub_row_end]
    assert "lane--primary" not in sub_row
    assert "lane-badge--primary" not in sub_row


@pytest.mark.regression
def test_live_fragment_without_main_lane_emits_no_primary_marker(
    pricing: PricingTable,
) -> None:
    """ux FRICTION-2 boundary: when no main lane exists, no primary badge appears.

    A subagent that started before the main session was observed (e.g. a
    transcript truncated at the top) must NOT be falsely promoted to "primary".
    """
    # A bare subagent dispatch + message, no main-lane event.
    state = fold_events(
        [
            _dispatch_event(0, "sub-only", agent_type="ux-evaluator"),
            _msg_event(1, "sub-only", "claude-sonnet-4-6", input_tokens=10, output_tokens=20),
        ],
        pricing,
    )
    html = render_live_fragment(state)
    assert "lane--primary" not in html
    assert "lane-badge--primary" not in html


@pytest.mark.regression
def test_live_css_carries_reduced_motion_guard() -> None:
    """The loading-pulse animation honours ``prefers-reduced-motion`` (a11y).

    A bare ``@keyframes`` with no opt-out would animate for users with
    vestibular-disorder accommodations; the CSS must include a media-query
    override. Surface-level guard: the keyframe + the media query are both
    present in the shell HTML's inline styles.
    """
    html = render_live_shell_html()
    assert "@keyframes tile-loading-pulse" in html
    assert "prefers-reduced-motion: reduce" in html


@pytest.mark.regression
def test_live_stream_panel_carries_kind_legend(pricing: PricingTable) -> None:
    """ux FRICTION-5 fold (REV-20260607-200447 → session 10e): the Live stream
    panel explains its raw ``Kind`` column values inline so the gatekeeper does
    not have to infer what ``turn`` / ``failure`` mean from context.

    Surface-level guard. The assertions pin:
    - the "Kind:" label is visible (intent over markup — a future restyle from
      ``<strong>`` to ``<span class="legend-label">`` is fine);
    - each enum token is wrapped in ``<code>`` (load-bearing for the visual
      distinction between enum value and gloss prose);
    - each gloss carries the load-bearing nuance: ``turn`` notes the
      uncosted-tier case (so the legend never claims every ``turn`` row is
      priced — the fold renderer appends uncosted turns to ``recent_events``
      too, with ``cost_usd=0.0``); ``failure`` cites the error class.
    A regression that removed the legend, renamed the tokens, dropped the
    uncosted-nuance phrasing, or stripped the ``<code>`` spans would fail.

    We route through ``render_live_fragment`` (not the private
    ``_render_live_stream_panel``) so the test also catches a transport-layer
    swap that bypassed the renderer entirely.
    """
    # Emit a real priced turn so the live-stream panel is in the DATA state
    # (an empty stream would render the absence tile instead of the legend).
    state = fold_events(
        [_msg_event(0, "main", "claude-opus-4-7", input_tokens=200, output_tokens=400)],
        pricing,
    )
    html = render_live_fragment(state)
    # Intent over markup: "Kind:" must appear, but the specific element is not
    # part of the contract (qa F1 fold from this review).
    assert "Kind:" in html
    # Enum tokens must render as inline code so the table-row "Kind" cell
    # values are visually distinct from the surrounding gloss prose.
    assert "<code>turn</code>" in html
    assert "<code>failure</code>" in html
    # Glosses must carry the load-bearing nuance.
    assert "assistant turn" in html
    # The uncosted-tier note is what makes the gloss honest for $0.0000 rows
    # (ux F1 fold from this review — without this clause the legend would
    # claim every "turn" row is priced, which is not what the fold model emits).
    assert "uncosted" in html
    assert "error or non-2xx event" in html


# --------------------------------------------------------------------------- #
# Live-render DIRECT unit tests (REV-20260607-200447 qa F1 fold → session 10i)
# --------------------------------------------------------------------------- #
#
# Phase 1's live-panel renderers were exercised only through ``render_live_fragment``
# composition (and the integration path via ``scripts/telemetry/dashboard_server.py``).
# qa F1 in the Phase 1 review called out that each sub-renderer needed direct,
# parameterized coverage of its own branches: a future edit could regress one
# sub-renderer's contract while the surrounding composition still produced
# plausible-looking HTML.
#
# These tests construct ``LiveState`` / ``RunwayGauge`` / ``AgentLane`` /
# ``LiveCostEvent`` synthetically (no ``fold_events``) so the renderer's
# behaviour is asserted independently of the fold's behaviour — a divergence
# between the two layers becomes a test failure rather than a silent mismatch.
# The complementary fold-driven tests above continue to guard the integration
# contract; these guards cover the renderer-as-pure-function contract.
#
# Surface-choice tradeoff (arch F1 from REV-20260608-013849 — session 10i):
# this section imports the FIVE private ``_render_*`` helpers across the
# tests/→src/telemetry boundary. The FRICTION-5 / FRICTION-2 tests above
# deliberately route through public ``render_live_fragment`` to catch a
# transport-layer swap that bypassed the renderer entirely; the qa F1 tests
# here deliberately route AROUND the public seam to catch per-sub-renderer
# regressions the composition wouldn't surface. Both choices are correct for
# the question they answer. The cost: a future refactor that re-homes a
# private renderer breaks these tests — Rule-of-Three keeps the symbols
# private (one caller file each, so they stay private until a second consumer
# emerges).


def _lane(
    lane_id: str,
    kind: str,
    status: str,
    *,
    agent_type: str | None = None,
    model: str | None = "claude-opus-4-7",
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cost_usd: float = 0.0,
    tool_count: int = 0,
    failure_count: int = 0,
) -> AgentLane:
    """Build an :class:`AgentLane` for a renderer-only test (no fold)."""
    return AgentLane(
        lane_id=lane_id,
        kind=kind,
        agent_type=agent_type,
        model=model,
        status=status,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cost_usd=cost_usd,
        tool_count=tool_count,
        failure_count=failure_count,
    )


# --- _render_runway_panel -------------------------------------------------- #


@pytest.mark.regression
def test_render_runway_panel_empty_context_window_renders_absence_tile() -> None:
    """qa F1: a zero ``context_window`` renders the honest-absence tile (spec R3a).

    The cold-start path: the dashboard has not yet seen a ``context`` event, so
    the gauge has no occupancy to render. Asserts the absence vocabulary is
    used (NOT a fabricated 0% bar — the C4 anti-pattern).
    """
    panel = _render_runway_panel(RunwayGauge())
    assert 'data-state="absent"' in panel
    assert "tile--absent" in panel
    assert "No live context snapshot yet." in panel
    # A fabricated 0% bar would be the C4 anti-pattern — pin it absent.
    assert "runway__fill" not in panel
    assert "runway__bar" not in panel
    assert 'data-state="data"' not in panel


@pytest.mark.regression
@pytest.mark.parametrize(
    ("status", "css_class", "label", "copy_fragment"),
    [
        (RUNWAY_OK, "runway--ok", "OK", "Plenty of headroom"),
        (RUNWAY_AMBER, "runway--amber", "warning", "Approaching wrap-up window"),
        (RUNWAY_RED, "runway--red", "critical", "Inside the wrap-up window"),
    ],
)
def test_render_runway_panel_status_emits_class_label_and_copy(
    status: str, css_class: str, label: str, copy_fragment: str
) -> None:
    """qa F1: each runway status emits the correct CSS modifier + manager label + copy.

    Spec R2 (runway gauge) requires distinct visual + textual signalling for the
    three states. The CSS class is the load-bearing decorative channel; the
    human-readable label + plain-language copy are the WCAG-1.4.1 textual
    channel a colour-deficient gatekeeper relies on. A regression that dropped
    the textual channel would silently break the colour-independent reading.
    """
    panel = _render_runway_panel(
        RunwayGauge(
            current_tokens=10_000,
            context_window=20_000,
            fill_pct=50.0,
            status=status,
            est_turns_remaining=12,
        )
    )
    assert css_class in panel
    assert f"&middot; {label}" in panel
    assert copy_fragment in panel
    # The data-tile container shape is intentionally the same across statuses —
    # only the modifier and the copy distinguish them (visual consistency).
    assert 'data-state="data"' in panel
    # The raw constant must NOT leak as the human-facing label (e.g. "amber"
    # would re-introduce the qa F2 / ux FRICTION-3 regression that the
    # _RUNWAY_LABEL translation map was added to prevent).
    if status != RUNWAY_OK:
        assert f"&middot; {status}<" not in panel


@pytest.mark.regression
def test_render_runway_panel_clamps_fill_pct_into_bar_width() -> None:
    """qa F1: ``runway.fill_pct`` outside [0, 100] is clamped before becoming a CSS width.

    A future bug that fed ``fill_pct`` directly to the ``style="width:..."``
    attribute could let a value like ``120`` overflow the bar container or a
    negative value invert the gauge. The renderer pins ``max(0.0, min(100.0,
    fill_pct))`` for the visual width while keeping the raw value in the
    headline (the data-honesty contract — the gatekeeper sees the true number,
    the bar stays inside its container).
    """
    over_panel = _render_runway_panel(
        RunwayGauge(
            current_tokens=24_000,
            context_window=20_000,
            fill_pct=120.0,
            status=RUNWAY_RED,
            est_turns_remaining=0,
        )
    )
    assert 'style="width:100.0%"' in over_panel
    # The raw value (not the clamped one) is the honest figure shown to the
    # gatekeeper — pinning it ensures the clamp does not silently rewrite the
    # data-honesty channel.
    assert ">120.0%</div>" in over_panel

    under_panel = _render_runway_panel(
        RunwayGauge(
            current_tokens=0,
            context_window=20_000,
            fill_pct=-5.0,
            status=RUNWAY_OK,
            est_turns_remaining=100,
        )
    )
    assert 'style="width:0.0%"' in under_panel


# --- _render_runway_estimate ---------------------------------------------- #


@pytest.mark.regression
def test_render_runway_estimate_cold_start_renders_honest_absence() -> None:
    """qa F1: ``est_turns_remaining=None`` renders the honest "not enough data" sentence.

    Cold-start cycle: no main-lane turn folded yet, so the rolling-average
    denominator is zero and the estimate is honestly ``None``. A regression
    that fabricated ``0`` or ``"unknown"`` would re-introduce the C4 anti-pattern
    the renderer was built to prevent.
    """
    est = _render_runway_estimate(RunwayGauge(est_turns_remaining=None))
    assert "not enough data yet" in est
    assert "needs at least one main-lane turn" in est
    # A fabricated "0 turns" or "unknown turns" headline would be the regression.
    assert "<strong>" not in est
    assert "uncosted" not in est


@pytest.mark.regression
def test_render_runway_estimate_with_value_renders_strong_int_and_method_note() -> None:
    """qa F1: a present ``est_turns_remaining`` renders as the bolded headline + method note.

    Pins both the typographic emphasis (a future restyle from ``<strong>`` to
    a CSS-only weight class would break this — and rightly so, the method note
    is the only way the gatekeeper sees the figure is a rolling average rather
    than a precise countdown) and the method note's substantive content.
    """
    est = _render_runway_estimate(RunwayGauge(est_turns_remaining=42))
    assert "<strong>42</strong>" in est
    assert "rolling avg of main-lane output tokens per turn" in est


# --- _render_agent_lanes_panel -------------------------------------------- #


@pytest.mark.regression
def test_render_agent_lanes_panel_no_main_and_no_agents_renders_absence_tile() -> None:
    """qa F1: an empty lane set renders the honest-absence tile (no data table).

    Pre-session state: nothing has been folded yet. The panel must NOT render
    an empty ``<table>`` (a regression that did so would leave the gatekeeper
    staring at headers with no rows — readable as "the dashboard is broken"
    rather than "no session yet").
    """
    panel = _render_agent_lanes_panel(LiveState())
    assert 'data-state="absent"' in panel
    assert "No active session yet." in panel
    # A regressed renderer might still emit the data-table shell; pin its
    # absence so a partial render doesn't slip through.
    assert "<table" not in panel
    assert "<tbody>" not in panel


@pytest.mark.regression
def test_render_agent_lanes_panel_with_main_only_renders_one_data_row() -> None:
    """qa F1: a main-lane-only state renders a single data row + table header.

    The boundary between "no session" (absence tile) and "main session active"
    (data tile) is load-bearing — a regression that kept rendering the absence
    tile until a subagent joined would hide the live main-session lane.
    """
    main = _lane("main", "main", LANE_ACTIVE, agent_type=None, output_tokens=500)
    panel = _render_agent_lanes_panel(LiveState(main=main))
    assert 'data-state="data"' in panel
    assert "<table" in panel
    # One row in the body — count <tr> entries between <tbody> and </tbody>.
    body = panel.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    assert body.count("<tr") == 1
    # The main lane carries the primary badge + class (see _render_agent_lane_row).
    assert "lane--primary" in panel


@pytest.mark.regression
def test_render_agent_lanes_panel_orders_main_first_then_subagents_in_dispatch_order() -> None:
    """qa F1: main lane renders first, then subagent lanes in dispatch order.

    The ordering contract: gatekeepers read top-down to assess "is the main
    session healthy?" first. A regression that sorted by lane_id or by status
    would scramble that read.
    """
    main = _lane("main", "main", LANE_ACTIVE)
    first = _lane("sub-A", "agent", LANE_ACTIVE, agent_type="qa-specialist")
    second = _lane("sub-B", "agent", LANE_COMPLETE, agent_type="security-specialist")
    panel = _render_agent_lanes_panel(LiveState(main=main, agents=(first, second)))
    assert (
        panel.index("<td>main</td>")
        < panel.index("<td>sub-A</td>")
        < panel.index("<td>sub-B</td>")
    )


# --- _render_agent_lane_row ----------------------------------------------- #


@pytest.mark.regression
@pytest.mark.parametrize(
    ("status", "expected_label_class", "expected_badge_text"),
    [
        (LANE_ACTIVE, "lane--active", "active"),
        (LANE_COMPLETE, "lane--complete", "complete"),
        (LANE_ORPHANED, "lane--orphaned", "orphaned"),
    ],
)
def test_render_agent_lane_row_emits_status_class_and_badge_label(
    status: str, expected_label_class: str, expected_badge_text: str
) -> None:
    """qa F1: each lane status emits the right CSS modifier + visible badge label.

    The badge text is the load-bearing channel (WCAG 1.4.1 — the row's tint is
    decorative reinforcement). The orphaned status in particular MUST surface
    as visible text because a colour-coded-only "orphaned" indicator would be
    invisible to a colour-deficient reader.

    qa F1 fold (REV-20260608-013905 — session 10i): the expected badge text is
    a literal string in the parametrize table — NOT ``f"...{status}..."``. The
    ``_LANE_STATUS_LABEL`` map exists precisely so the raw constant + the
    human-facing label can diverge; if the constant ``LANE_ORPHANED`` were
    ever renamed to ``"orphan"`` while the map kept ``"orphaned"`` as the
    label, an f-string-interpolated assertion would silently flip its
    expectation. Pinning the literal label catches that.
    """
    lane = _lane("sub-test", "agent", status, agent_type="qa-specialist")
    row = _render_agent_lane_row(lane)
    assert expected_label_class in row
    assert f'<span class="lane-badge">{expected_badge_text}</span>' in row


@pytest.mark.regression
def test_render_agent_lane_row_unknown_status_falls_back_to_raw_constant() -> None:
    """qa F2 fold (REV-20260608-013905 — session 10i): an out-of-map lane status
    falls back to the raw constant for both the CSS modifier and the badge text.

    ``_render_agent_lane_row`` uses ``_LANE_STATUS_LABEL.get(lane.status,
    lane.status)`` — the fallback. If a future ``live.py`` extension adds a
    new status (e.g. ``"pending"``) before the dashboard's translation map is
    updated, the row must render it visibly (raw constant), not silently drop
    it. A regression that switched to ``_LANE_STATUS_LABEL[lane.status]``
    would raise ``KeyError`` on the new status and crash the renderer; this
    test guards the documented forward-compat path.
    """
    lane = _lane("sub-test", "agent", "pending", agent_type="qa-specialist")
    row = _render_agent_lane_row(lane)
    assert "lane--pending" in row
    assert '<span class="lane-badge">pending</span>' in row


@pytest.mark.regression
def test_render_agent_lane_row_main_lane_carries_primary_class_and_badge() -> None:
    """qa F1: a ``kind="main"`` lane carries ``lane--primary`` + a ``primary`` text badge.

    Differentiates the main session from dispatched subagents — same contract
    as the existing FRICTION-2 integration test, but exercised on the renderer
    directly (the FRICTION-2 test routes through ``render_live_fragment``).
    """
    lane = _lane("main", "main", LANE_ACTIVE, agent_type=None)
    row = _render_agent_lane_row(lane)
    assert "lane--primary" in row
    assert 'class="lane-badge lane-badge--primary">primary</span>' in row
    # When agent_type is None on the main lane, the rendered agent cell shows
    # "main" — not "—" (the em-dash absence marker used for subagents) and not
    # the empty string (which would silently disappear from the table).
    assert "<td>main" in row


@pytest.mark.regression
def test_render_agent_lane_row_subagent_with_missing_agent_type_renders_emdash() -> None:
    """qa F1: a subagent lane with ``agent_type=None`` renders ``—`` (not empty / not "main").

    A renderer that defaulted to ``"main"`` on missing agent_type would falsely
    promote a subagent to primary; one that defaulted to empty string would
    silently elide the cell. The em-dash is the honest absence marker.
    """
    lane = _lane("sub-anon", "agent", LANE_ACTIVE, agent_type=None, model=None)
    row = _render_agent_lane_row(lane)
    assert "<td>—</td>" in row
    # Model also defaults to em-dash when missing — same absence vocabulary.
    assert row.count("<td>—</td>") >= 2
    # And the lane must NOT carry the primary marker.
    assert "lane--primary" not in row
    assert "lane-badge--primary" not in row


@pytest.mark.regression
def test_render_agent_lane_row_escapes_dynamic_string_fields() -> None:
    """qa F1: every dynamic string field passes through ``_esc`` (spec C6).

    The lane_id / agent_type / model are transcript-shaped (the dispatch
    tool_id, the developer-supplied subagent type, the model ID from the API).
    A regression that interpolated any of them raw would be stored-XSS in the
    rendered fragment. Mirrors the existing failure/divergence injection
    guards above, applied to the lane-row surface qa F1 specifically called out.
    """
    payload = "<script>alert(1)</script>"
    lane = _lane(payload, "agent", LANE_ACTIVE, agent_type=payload, model=payload)
    row = _render_agent_lane_row(lane)
    # Raw payload must NOT appear; escaped form must appear in each of the
    # three dynamic-string cells.
    assert "<script>" not in row
    assert row.count("&lt;script&gt;alert(1)&lt;/script&gt;") == 3


@pytest.mark.regression
def test_render_agent_lane_row_total_tokens_sums_input_output_and_cache_read() -> None:
    """qa F1: the rendered token total = input + output + cache_read (NOT cache_create).

    The cache_create tokens are excluded from the lane's headline token
    figure because they are a one-time write-side cost the fold already prices
    separately. A regression that added cache_create here would silently
    inflate every lane's token figure.
    """
    lane = _lane(
        "main",
        "main",
        LANE_ACTIVE,
        input_tokens=200,
        output_tokens=400,
        cache_read_tokens=1_000,
        cost_usd=0.0625,
        tool_count=3,
        failure_count=1,
    )
    row = _render_agent_lane_row(lane)
    # 200 + 400 + 1000 = 1,600 — pinned with the thousands separator.
    assert '<td class="num">1,600</td>' in row
    # Cost rendered at 4 decimal places via _fmt_usd.
    assert '<td class="num">$0.0625</td>' in row
    # Tool and failure counts render via _fmt_int (always present, never None).
    assert '<td class="num">3</td>' in row
    assert '<td class="num">1</td>' in row


# --- _render_live_stream_panel -------------------------------------------- #


@pytest.mark.regression
def test_render_live_stream_panel_empty_renders_absence_tile() -> None:
    """qa F1: an empty event stream renders the honest-absence tile, not an empty table.

    A regression that always rendered the table shell would leave the panel
    with headers but no body — a "broken dashboard" signal rather than the
    honest "no live events yet" cold-start state.
    """
    panel = _render_live_stream_panel(())
    assert 'data-state="absent"' in panel
    assert "No live events yet." in panel
    assert "<table" not in panel
    assert "<tbody>" not in panel


@pytest.mark.regression
def test_render_live_stream_panel_emits_rows_most_recent_first() -> None:
    """qa F1: rendered rows appear MOST-RECENT FIRST (reverse of the fold order).

    The fold appends to ``recent_events`` in chronological order (oldest first
    → newest last); the renderer reverses to put the most-recent at the top so
    the gatekeeper's eye lands on the latest event without scrolling. A
    regression that dropped the ``reversed()`` would silently show the oldest
    event at the top of every panel.
    """
    base = datetime(2026, 6, 8, 1, 0, 0, tzinfo=UTC)
    events = (
        LiveCostEvent(timestamp=base, lane_id="main", kind="turn", cost_usd=0.10, tokens=1_000),
        LiveCostEvent(
            timestamp=base + timedelta(seconds=30),
            lane_id="sub-A",
            kind="turn",
            cost_usd=0.05,
            tokens=500,
        ),
        LiveCostEvent(
            timestamp=base + timedelta(minutes=1),
            lane_id="main",
            kind="failure",
            cost_usd=0.0,
            tokens=0,
        ),
    )
    panel = _render_live_stream_panel(events)
    assert 'data-state="data"' in panel
    body = panel.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    # The failure event's ISO timestamp must precede the first turn's in the body.
    failure_idx = body.index("2026-06-08T01:01:00")
    middle_idx = body.index("2026-06-08T01:00:30")
    oldest_idx = body.index("2026-06-08T01:00:00")
    assert failure_idx < middle_idx < oldest_idx


@pytest.mark.regression
def test_render_live_stream_panel_renders_uncosted_turn_as_zero_dollars_at_4_places() -> None:
    """qa F1: an uncosted turn renders cost at 4 decimals (``$0.0000``), not "uncosted".

    The live stream's per-row cost is a concrete ``float`` (the fold ALWAYS
    bumps ``cost_usd`` on ``LiveCostEvent`` — uncosted means 0.0, not None);
    the panel's per-row cell uses ``_fmt_usd(..., places=4)``. The "uncosted"
    nuance lives in the ``recent_events`` aggregate accounting (where uncosted
    turns are counted separately) and in the kind-legend gloss the FRICTION-5
    fold pinned above. A regression that switched the per-row cell to "uncosted"
    would lie about a row that genuinely accrued zero cost (e.g. a failure).
    """
    base = datetime(2026, 6, 8, 1, 0, 0, tzinfo=UTC)
    panel = _render_live_stream_panel(
        (
            LiveCostEvent(
                timestamp=base,
                lane_id="main",
                kind="turn",
                cost_usd=0.0,
                tokens=1_200,
            ),
        )
    )
    body = panel.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    assert '<td class="num">$0.0000</td>' in body
    assert "uncosted" not in body
    # The token count renders with thousands separator via _fmt_int.
    assert '<td class="num">1,200</td>' in body


@pytest.mark.regression
def test_render_live_stream_panel_escapes_dynamic_string_fields() -> None:
    """qa F1: lane_id + kind in a row pass through ``_esc`` (spec C6).

    A failure event's ``kind`` is the constant ``"failure"`` today, but
    ``lane_id`` is the dispatch tool_id (transcript-shaped). The escape seam
    must be uniform across both fields so a regression that swapped a single
    interpolation back to an f-string is caught.
    """
    payload = "<img src=x onerror=alert(1)>"
    base = datetime(2026, 6, 8, 1, 0, 0, tzinfo=UTC)
    panel = _render_live_stream_panel(
        (
            LiveCostEvent(
                timestamp=base,
                lane_id=payload,
                kind=payload,
                cost_usd=0.01,
                tokens=10,
            ),
        )
    )
    assert "<img src=x" not in panel
    # Escaped form must appear twice — once in the lane_id cell, once in the kind cell.
    escaped = "&lt;img src=x onerror=alert(1)&gt;"
    assert panel.count(escaped) == 2


# --- render_live_fragment composition ------------------------------------ #


@pytest.mark.regression
def test_render_live_fragment_empty_state_emits_four_absence_tiles() -> None:
    """qa F1 composition: an empty :class:`LiveState` produces exactly four absence tiles.

    The first-paint guarantee: when no fold has happened yet, the live section
    must show four distinct honest-absence tiles (runway / agent lanes / live
    stream / per-turn cost chart), not a half-rendered data table or a single
    combined tile. The fragment must still be ONE root ``<section>`` for the
    htmx outerHTML swap.

    Phase 2 NEXT slice (wire-the-chart) added the per-turn cost chart panel —
    on first paint it renders the same honest-absence vocabulary as the other
    three panels, never a fabricated empty chart with phantom axes (the C4
    anti-pattern). Bumping ``count == 3`` to ``count == 4`` here is the
    contract-strengthening side of that addition: a future regression that
    dropped the chart panel's absence tile would fail this count alongside
    the missing "No priced turns yet." copy assertion.
    """
    html = render_live_fragment(LiveState())
    # One <section> root (htmx swap target shape).
    assert html.startswith('<section id="live-section"')
    assert html.endswith("</section>")
    assert html.count('<section id="live-section"') == 1
    # Four absence tiles — one per panel (runway / lanes / stream / chart).
    assert html.count('data-state="absent"') == 4
    # None of the data-tile or loading-tile vocabulary appears in the empty
    # composition. The chart panel is in ``tile--absent`` state (not
    # ``tile--loading``) because the absence vs interim-loading distinction is
    # genuine: absent = no data exists yet; loading = data exists, chart
    # rendering layer not yet active.
    assert 'data-state="data"' not in html
    assert 'data-state="loading"' not in html
    # The four absence copies are each present, so the gatekeeper can tell
    # which panel is absent at a glance.
    assert "No live context snapshot yet." in html
    assert "No active session yet." in html
    assert "No live events yet." in html
    assert "No priced turns yet." in html
    # And specifically: NO <canvas> on first paint (the chart panel is in
    # absence mode, not a fabricated empty chart).
    assert "<canvas" not in html
    # NO <script type="application/json"> data block either — the empty-state
    # path must not bake a `[]` payload that the init script would still try
    # to render (a phantom empty chart is the C4 anti-pattern).
    assert 'type="application/json"' not in html


@pytest.mark.regression
def test_render_live_fragment_composes_runway_then_lanes_then_stream_then_chart() -> None:
    """qa F1 composition: panels render in runway -> lanes -> stream -> chart order.

    The visual hierarchy is load-bearing — the runway is the highest-stakes
    signal (gatekeeper decides when to hand off), the agent lanes are the
    operational state, the live stream is the per-event trail, and the per-turn
    cost chart is the trend visualisation derived FROM the stream above it
    (the chart sits last because a reader who has not yet scanned the stream
    can still read the chart, but the stream remains the source of truth for
    the chart's bars/points). A regression that reordered the composition
    would silently change the reading flow.

    Phase 2 NEXT slice (wire-the-chart) extended this from 3 to 4 panels — the
    composition test now pins the full hierarchy chain so a future drop of the
    chart panel (or a re-order that placed the chart above the stream) fails
    here at the index-ordering step, not only at the count step.
    """
    main = _lane("main", "main", LANE_ACTIVE, output_tokens=400)
    runway = RunwayGauge(
        current_tokens=10_000,
        context_window=20_000,
        fill_pct=50.0,
        status=RUNWAY_AMBER,
        est_turns_remaining=10,
    )
    events = (
        LiveCostEvent(
            timestamp=datetime(2026, 6, 8, 1, 0, 0, tzinfo=UTC),
            lane_id="main",
            kind="turn",
            cost_usd=0.05,
            tokens=400,
        ),
    )
    state = LiveState(main=main, runway=runway, recent_events=events)
    html = render_live_fragment(state)
    # Runway panel heading appears before the agent-lanes heading, which
    # appears before the live-stream heading, which appears before the
    # per-turn cost chart heading.
    runway_idx = html.index("<h3>Context runway</h3>")
    lanes_idx = html.index("<h3>Agent lanes</h3>")
    stream_idx = html.index("<h3>Live stream</h3>")
    chart_idx = html.index("<h3>Per-turn cost over time</h3>")
    assert runway_idx < lanes_idx < stream_idx < chart_idx
    # All four panels are populated — no absence tiles for this case.
    assert 'data-state="absent"' not in html
    # Three DATA panels (runway / lanes / stream) + ONE LOADING panel (chart).
    # **This is permanent at the Python render layer** — the per-turn cost
    # chart's ``data-state="loading"`` is the wire format the renderer emits;
    # the init script at ``/static/dashboard-chart.js`` flips it to
    # ``"data"`` at RUNTIME on first successful draw (not testable from
    # Python — runtime DOM mutation). Do NOT change to ``== 4`` without
    # also changing the renderer to emit ``tile--data`` directly; that
    # change is blocked by the regression-ledger entry from
    # REV-20260608-025749 ("Do not promote the chart back to
    # ``data-state='data'`` without ALSO removing the hidden attribute on
    # the render-target wrapper and shipping the init script in the same
    # commit"). Step 4 shipped the init script in the same commit; the
    # ledger invariant remains in force.
    assert html.count('data-state="data"') == 3
    assert html.count('data-state="loading"') == 1


# --------------------------------------------------------------------------- #
# Per-turn cost chart panel — DIRECT unit tests (Phase 2 wire-the-chart slice)
# --------------------------------------------------------------------------- #
#
# The new ``_render_per_turn_cost_chart_panel`` reuses the session 10i pattern:
# synthetic ``LiveCostEvent`` tuples (no ``fold_events``) so each branch of the
# renderer's contract is asserted independent of the fold's behaviour. The
# composition tests above route through ``render_live_fragment`` and catch a
# panel that was dropped from the section; these tests route AROUND the public
# seam to catch a regression INSIDE the new panel that the surrounding
# composition would silently mask.
#
# The Chart.js init script (src/telemetry/static/dashboard-chart.js, shipped
# step 4 / commit e70cfd3) consumes this JSON payload via document.getElementById
# on the pinned data-block + canvas ids. These tests pin the id strings and the
# JSON shape as the known-good Python↔JS integration surface; a rename or shape
# change in dashboard.py must be reflected in dashboard-chart.js + here in
# lockstep (see arch F3 comment in dashboard-chart.js — Python is the source of
# truth, the JS file and these tests are copies kept in sync by code review).


@pytest.mark.regression
def test_render_per_turn_cost_chart_panel_empty_events_renders_absence_tile() -> None:
    """Empty events tuple renders the honest-absence tile (spec R3a / C4).

    First-paint: no events folded yet, so no priced turns exist to chart. The
    panel renders the same dashed-border absence vocabulary as the runway /
    lanes / stream panels above it — NOT a fabricated empty chart with phantom
    axes (the C4 anti-pattern the Phase 2 build must not regress).
    """
    panel = _render_per_turn_cost_chart_panel(())
    assert 'data-state="absent"' in panel
    assert "tile--absent" in panel
    assert "No priced turns yet." in panel
    # Heading carries the time-dimension framing (ux F4 fold from
    # REV-20260608-025749) so the gatekeeper reads the panel as a TREND view,
    # not a scalar.
    assert "Per-turn cost over time" in panel
    # No data-tile or loading-tile vocabulary, no canvas, no JSON data block.
    assert 'data-state="data"' not in panel
    assert 'data-state="loading"' not in panel
    assert "<canvas" not in panel
    assert 'type="application/json"' not in panel
    # qa F3 (REV-20260608-044128 → REV-20260608-045732 qa F1 fold): the Python
    # renderer takes the ``if not priced_points: return absence_html`` exit
    # BEFORE constructing any ``<script type="application/json">`` data block,
    # so neither the media-type marker (asserted above) nor any JSON content
    # (including the empty-array literal ``[]``) appears in the absence output.
    # This guards the STRUCTURAL invariant — "no JSON scaffolding reaches the
    # absence path" — not a substring coincidence: a future regression that
    # bypasses the absence exit AND emits an empty-array stub would have to
    # leak ``[]`` somewhere, and this assertion catches it.
    assert "[]" not in panel


@pytest.mark.regression
def test_render_per_turn_cost_chart_panel_only_failure_events_renders_absence_tile() -> None:
    """A stream of only ``kind="failure"`` events renders the absence tile.

    The chart's domain is per-turn cost — a failure-kind event has no per-turn
    cost dimension to chart. The renderer filters ``kind == "turn"`` BEFORE the
    absence decision; an all-failure stream is therefore equivalent to an
    empty turn stream and renders the absence tile (NOT a chart with zero
    data points).

    Defensive guard: today ``_bump_totals`` only appends ``kind="turn"`` events
    (see src/telemetry/live.py:371 + the LiveCostEvent docstring), but the model
    allows ``kind="failure"`` (live.py:171 "turn" | "failure"). A future
    failure-emitting fold landing on this renderer without the filter would
    otherwise produce a chart of zero-cost failure points.
    """
    base = datetime(2026, 6, 8, 1, 0, 0, tzinfo=UTC)
    events = (
        LiveCostEvent(timestamp=base, lane_id="main", kind="failure", cost_usd=0.0, tokens=0),
        LiveCostEvent(
            timestamp=base + timedelta(seconds=1),
            lane_id="agent-1",
            kind="failure",
            cost_usd=0.0,
            tokens=0,
        ),
    )
    panel = _render_per_turn_cost_chart_panel(events)
    assert 'data-state="absent"' in panel
    assert "No priced turns yet." in panel
    assert "<canvas" not in panel
    assert 'type="application/json"' not in panel


@pytest.mark.regression
def test_render_per_turn_cost_chart_panel_emits_canvas_and_data_block_when_populated() -> None:
    """Populated turn events render a canvas + JSON data block with pinned ids.

    The two ids ``per-turn-cost-chart`` (canvas) and ``per-turn-cost-data``
    (script block) are the integration surface the Phase 2 Chart.js init slice
    will look up via ``document.getElementById``. A regression that renamed
    either id would silently break the init script — pin them both here so
    the rename is caught before the integration lands.
    """
    base = datetime(2026, 6, 8, 1, 0, 0, tzinfo=UTC)
    events = (
        LiveCostEvent(timestamp=base, lane_id="main", kind="turn", cost_usd=0.0123, tokens=400),
    )
    panel = _render_per_turn_cost_chart_panel(events)
    # ux F1 (REV-20260608-025749 fold): tile--loading + data-state="loading"
    # is the wire format the Python renderer emits PERMANENTLY — the init
    # script at /static/dashboard-chart.js flips it to ``"data"`` at runtime
    # on first successful draw (the runtime mutation is not testable from
    # Python; the load-order regression test in test_telemetry.py pins the
    # init-script tag is wired into the shell head). Guards the gatekeeper
    # from a blank canvas during the brief window before the first
    # ``htmx:afterSwap`` event fires.
    assert 'data-state="loading"' in panel
    assert "tile--loading" in panel
    assert 'data-state="data"' not in panel
    # Canvas id is pinned (init script lookup surface).
    assert 'id="per-turn-cost-chart"' in panel
    assert "<canvas" in panel
    # ux F2 fold: WCAG SC 1.1.1/4.1.2 — accessible name + role + fallback text.
    assert 'role="img"' in panel
    assert 'aria-label="' in panel
    # JSON data block id + media type are pinned (init script lookup surface).
    assert 'id="per-turn-cost-data"' in panel
    assert 'type="application/json"' in panel
    # The canvas + data block are inside the hidden render-target wrapper as
    # the Python renderer's PERMANENT wire format; the init script at
    # /static/dashboard-chart.js removes the ``hidden`` attribute and flips
    # the tile to ``data-state="data"`` on first successful draw. Together
    # with the loading-copy below, this prevents the gatekeeper from seeing
    # a blank canvas during the brief window before the first htmx swap.
    assert 'class="chart-rendering-target" hidden' in panel
    # Loading-copy explains what the user is seeing.
    assert "Chart visualization layer initializing" in panel
    # No absence vocabulary leaks into the data path.
    assert 'data-state="absent"' not in panel
    # Heading carries the time-dimension framing (ux F4 fold).
    assert "<h3>Per-turn cost over time</h3>" in panel


@pytest.mark.regression
def test_render_per_turn_cost_chart_panel_json_payload_carries_t_cost_lane_id() -> None:
    """JSON payload shape: ``t`` iso, ``cost`` float, ``lane_id`` str, ``uncosted`` bool.

    Pin the data contract the Phase 2 init script will consume. Order is
    chronological (oldest first) so the X-axis line chart reads left-to-right
    as time progresses. The renderer applies ``</`` → ``<\\/`` to the JSON
    body, so the assertion uses ``json.loads`` after re-substituting ``</``
    back in (the round-trip JSON value, not the on-the-wire bytes).

    The ``uncosted`` field (arch F1 fold) is part of the contract: a priced
    cheap turn carries ``uncosted: false`` and an unpriced-tier turn carries
    ``uncosted: true``, so the init script can render them distinctly. See
    the dedicated arch-F1 regression test below for the per-event semantics.
    """
    base = datetime(2026, 6, 8, 1, 0, 0, tzinfo=UTC)
    events = (
        LiveCostEvent(timestamp=base, lane_id="main", kind="turn", cost_usd=0.05, tokens=400),
        LiveCostEvent(
            timestamp=base + timedelta(seconds=30),
            lane_id="agent-qa",
            kind="turn",
            cost_usd=0.0,
            tokens=50,
        ),
        LiveCostEvent(
            timestamp=base + timedelta(seconds=60),
            lane_id="main",
            kind="turn",
            cost_usd=0.075,
            tokens=600,
        ),
    )
    panel = _render_per_turn_cost_chart_panel(events)
    # Extract the JSON payload between the data-block script tags.
    start_marker = 'id="per-turn-cost-data" type="application/json">'
    start = panel.index(start_marker) + len(start_marker)
    end = panel.index("</script>", start)
    payload_bytes = panel[start:end]
    # The on-the-wire payload must NOT contain a literal `</` (the </script>
    # injection guard); the JSON-round-trip path re-substitutes for parsing.
    # See the dedicated injection test below for the strict guard assertion.
    points = json.loads(payload_bytes.replace("<\\/", "</"))
    assert isinstance(points, list)
    assert len(points) == 3
    # Chronological order (oldest first — X-axis reads left-to-right).
    assert points[0]["t"] == base.isoformat()
    assert points[2]["t"] == (base + timedelta(seconds=60)).isoformat()
    # Field shape pinned: t / cost / lane_id / uncosted on every entry.
    for entry in points:
        assert set(entry) == {"t", "cost", "lane_id", "uncosted"}
        assert isinstance(entry["t"], str)
        assert isinstance(entry["cost"], (int, float))
        assert isinstance(entry["lane_id"], str)
        assert isinstance(entry["uncosted"], bool)
    # Specific values pinned (catches a future re-key that mapped cost to
    # tokens or vice versa).
    assert points[0]["lane_id"] == "main"
    assert points[0]["cost"] == 0.05
    assert points[1]["lane_id"] == "agent-qa"
    assert points[1]["cost"] == 0.0
    assert points[2]["cost"] == 0.075
    # Default ``uncosted=False`` on synthetic events — the dedicated arch-F1
    # test exercises the True branch end-to-end through ``fold_events``.
    for entry in points:
        assert entry["uncosted"] is False


@pytest.mark.regression
def test_render_per_turn_cost_chart_panel_filters_failure_events_out_of_payload() -> None:
    """A mixed stream of turn + failure events bakes ONLY the turn events.

    The chart's domain is per-turn cost; failure-kind events have no cost
    dimension to chart and would otherwise appear as phantom zero-cost data
    points. A future regression that dropped the ``kind == "turn"`` filter
    would silently introduce failure events into the chart — pinning the
    filter at the data-shape boundary catches that before the init script
    has a chance to render the wrong series.
    """
    base = datetime(2026, 6, 8, 1, 0, 0, tzinfo=UTC)
    events = (
        LiveCostEvent(timestamp=base, lane_id="main", kind="turn", cost_usd=0.05, tokens=400),
        LiveCostEvent(
            timestamp=base + timedelta(seconds=10),
            lane_id="main",
            kind="failure",
            cost_usd=0.0,
            tokens=0,
            detail="HTTP 500",
        ),
        LiveCostEvent(
            timestamp=base + timedelta(seconds=20),
            lane_id="agent-1",
            kind="turn",
            cost_usd=0.01,
            tokens=80,
        ),
    )
    panel = _render_per_turn_cost_chart_panel(events)
    start_marker = 'id="per-turn-cost-data" type="application/json">'
    start = panel.index(start_marker) + len(start_marker)
    end = panel.index("</script>", start)
    points = json.loads(panel[start:end].replace("<\\/", "</"))
    # Two turn events; the one failure event is filtered out.
    assert len(points) == 2
    assert points[0]["lane_id"] == "main"
    assert points[0]["cost"] == 0.05
    assert points[1]["lane_id"] == "agent-1"
    assert points[1]["cost"] == 0.01
    # The failure event's detail string ("HTTP 500") must not appear in the
    # baked payload — defense in depth against a future filter regression
    # that included the kind/detail fields.
    assert "HTTP 500" not in panel


@pytest.mark.regression
def test_render_per_turn_cost_chart_panel_resists_script_close_injection_in_lane_id() -> None:
    """Spec R11 / security F2: ``</script><script>`` in ``lane_id`` cannot close the block.

    The chart data block uses ``<script type="application/json">`` — non-executable
    per the type attribute, but HTML5 still parses the body in raw-text mode and
    ends the block on the literal byte sequence ``</`` followed by a name match.
    A transcript-shaped ``lane_id`` carrying ``</script><script>alert(1)</script>``
    must NOT close the data block, OR an attacker would land an active inline
    ``<script>`` AFTER it — the CSP ``script-src 'self'`` (no ``'unsafe-inline'``)
    would still block execution, but the rule is defense-in-depth: the escape
    guard is the first line, CSP is the second.

    The fix (spec R11): ``json.dumps`` followed by replacing every ``</`` with
    ``<\\/``. The escaped ``\\/`` form is valid JSON per RFC 8259 §7 and
    round-trips through ``JSON.parse`` unchanged, so the chart still receives
    the original string — only the raw HTML byte sequence is broken.
    """
    payload = '</script><script>alert("xss")</script>'
    base = datetime(2026, 6, 8, 1, 0, 0, tzinfo=UTC)
    events = (
        LiveCostEvent(timestamp=base, lane_id=payload, kind="turn", cost_usd=0.01, tokens=10),
    )
    panel = _render_per_turn_cost_chart_panel(events)
    # The on-the-wire panel HTML must contain EXACTLY ONE </script> — the one
    # that closes the data block itself. The injected payload's two </script>
    # tokens must have been neutralised to <\/script>.
    assert panel.count("</script>") == 1
    # The neutralised form appears twice in the data block body (once per
    # injected </script> token) — pin it explicitly so a future regression
    # that swapped the escape for `html.escape` (which would emit `&lt;/`
    # instead) fails here.
    assert panel.count("<\\/script>") == 2
    # JSON.parse round-trip: re-substituting `<\/` back to `</` and parsing
    # must yield the original payload string unchanged.
    start_marker = 'id="per-turn-cost-data" type="application/json">'
    start = panel.index(start_marker) + len(start_marker)
    end = panel.index("</script>", start)
    points = json.loads(panel[start:end].replace("<\\/", "</"))
    assert len(points) == 1
    assert points[0]["lane_id"] == payload
    # No literal `<script>` appears AFTER the closing </script> of the data
    # block — would indicate a successful injection.
    after_data_block = panel[end + len("</script>") :]
    assert "<script>" not in after_data_block


@pytest.mark.regression
def test_render_per_turn_cost_chart_panel_rejects_non_finite_cost_usd() -> None:
    """Spec R11 + RFC 8259 §3 (qa F3 + security F1 fold from REV-20260608-025749).

    Python's ``json.dumps`` with the default ``allow_nan=True`` silently emits
    bare ``NaN`` / ``Infinity`` tokens for non-finite floats — these are NOT
    valid RFC 8259, and ``JSON.parse`` throws ``SyntaxError`` in every browser.
    ``LiveCostEvent.cost_usd`` is a plain ``float`` (no field validator on the
    frozen dataclass), so a non-finite value reaching the renderer is possible
    even though the fold path constrains it. Defense-in-depth: ``allow_nan=False``
    converts silent corruption into a loud ``ValueError`` at render time, which
    the FastAPI error middleware catches as a generic 500.

    Two specialists (qa-specialist + security-specialist) independently raised
    this finding from orthogonal directions — qa on data-integrity, security on
    the injection surface (a bare ``NaN`` token in a parser-data context). The
    test pins both ``float("nan")`` and ``float("inf")`` so a future regression
    that dropped ``allow_nan=False`` fails on either path.
    """
    base = datetime(2026, 6, 8, 1, 0, 0, tzinfo=UTC)
    for bad_cost in (float("nan"), float("inf"), float("-inf")):
        ev = LiveCostEvent(
            timestamp=base, lane_id="main", kind="turn", cost_usd=bad_cost, tokens=10
        )
        with pytest.raises(ValueError):
            _render_per_turn_cost_chart_panel((ev,))


@pytest.mark.regression
def test_render_per_turn_cost_chart_panel_canvas_carries_accessible_name_and_role() -> None:
    """WCAG SC 1.1.1 (Non-text content) + 4.1.2 (Name+Role) — ux F2 fold.

    A ``<canvas>`` element with no ``aria-label``, no ``role="img"``, and no
    fallback content is invisible to screen readers. The surrounding ``<p>``
    legend is a sibling, NOT a label association — assistive tech does not
    connect them. This test pins the WCAG AA accessibility contract:
    ``role="img"`` + a descriptive ``aria-label`` that says WHAT the chart
    plots (per-turn cost over time), plus a fallback ``<p>`` inside the
    canvas for legacy / canvas-disabled clients. A regression that dropped
    any of these three channels would silently re-introduce the WCAG defect.
    """
    base = datetime(2026, 6, 8, 1, 0, 0, tzinfo=UTC)
    events = (
        LiveCostEvent(timestamp=base, lane_id="main", kind="turn", cost_usd=0.01, tokens=10),
    )
    panel = _render_per_turn_cost_chart_panel(events)
    # role="img" is the assistive-tech role assignment for canvas-shaped content.
    assert 'role="img"' in panel
    # aria-label carries the descriptive content the screen reader announces.
    # The label must MEANINGFULLY describe the chart, not just repeat the title.
    assert 'aria-label="' in panel
    assert "per-turn cost" in panel.lower()
    assert "line chart" in panel.lower()
    # Fallback content INSIDE the canvas (browsers without canvas support,
    # screen readers that expose inner content).
    canvas_start = panel.index("<canvas")
    canvas_end = panel.index("</canvas>")
    canvas_body = panel[canvas_start:canvas_end]
    assert "<p>" in canvas_body
    assert "data available" in canvas_body.lower()


@pytest.mark.regression
def test_render_per_turn_cost_chart_panel_legend_does_not_cross_reference_other_panels() -> None:
    """ux F3 fold from REV-20260608-025749 — panel legend is self-contained.

    The original legend ended with "(the per-event uncosted-vs-priced nuance
    lives in the live-stream panel's legend above)" — a cross-panel reference
    that used internal-vocabulary ("nuance") and had no visual anchor. Per the
    teach-don't-dump feedback memory, gatekeeper-facing copy must define terms
    inline. Folded: the legend now explains uncosted directly ("Turns from
    model tiers without a known price appear at 0.0000 — uncosted, excluded
    from totals, not zero-rated"). This regression test pins the negative
    surface so a future revert to the cross-reference form fails here.
    """
    base = datetime(2026, 6, 8, 1, 0, 0, tzinfo=UTC)
    events = (LiveCostEvent(timestamp=base, lane_id="main", kind="turn", cost_usd=0.0, tokens=10),)
    panel = _render_per_turn_cost_chart_panel(events)
    # The "nuance" vocabulary must be absent (internal-jargon → gatekeeper UX).
    assert "nuance" not in panel.lower()
    # The cross-panel reference must be absent (no scroll-up-to-another-panel
    # instruction in the chart legend).
    assert "live-stream panel" not in panel.lower()
    # The inline definition of uncosted must be present, complete with the
    # load-bearing clause "excluded from totals, not zero-rated" mirroring
    # the cost panel's accounting honesty.
    assert "excluded from totals" in panel.lower()
    assert "zero-rated" in panel.lower()


@pytest.mark.regression
def test_render_live_shell_html_includes_chartjs_script_tag() -> None:
    """Spec R11a: the shell embeds the vendored Chart.js script tag, ``defer`` loaded.

    The chart's runtime loads from the local static mount — NEVER a CDN — paired
    with htmx in the same shell <head>. ``defer`` so it does not block initial
    paint; ``Chart`` is in scope by the time htmx swaps in the first
    ``/fragments/live`` fragment. The shell carries no chart-specific markup
    beyond this script-tag load — all chart data is baked INTO the fragment as
    a JSON literal (see _render_per_turn_cost_chart_panel).
    """
    shell = render_live_shell_html(generated_label="2026-06-08 12:00 UTC")
    # Pinned to the load form — `src="/static/chart.umd.min.js"` is the
    # contract; the `defer` attribute is the load-order guarantee.
    assert '<script src="/static/chart.umd.min.js" defer></script>' in shell
    # htmx is still there (sibling-load — neither replaces the other).
    assert '<script src="/static/htmx.min.js" defer></script>' in shell
    # The pair sits in the <head>, before the inline <style> block.
    chart_idx = shell.index("/static/chart.umd.min.js")
    style_idx = shell.index("<style>")
    assert chart_idx < style_idx


@pytest.mark.regression
def test_render_live_shell_html_includes_dashboard_chart_init_script_tag() -> None:
    """Phase 2 step 4 (CSP fork option a — VENDORED-INIT): the shell wires the
    first-party ``dashboard-chart.js`` init script after the Chart.js library.

    Load-order contract (load-bearing): with ``defer``, browsers execute scripts
    in document order, so the Chart global is guaranteed defined when the init
    script's IIFE runs. A future regression that reorders these tags (or drops
    ``defer``) breaks that guarantee silently — Chart-undefined at IIFE time
    causes the init script's early return, the chart stays in the loading
    state forever, and the static fragment tests still pass.

    CSP contract (load-bearing): the script lives under the existing
    ``script-src 'self'`` policy as a same-origin asset; this test pinning the
    ``src="/static/dashboard-chart.js"`` path is part of how we keep the CSP
    decision (option a) honoured — a future move to inline init code would
    fail this assertion AND would require a CSP relaxation review (option b).
    """
    shell = render_live_shell_html(generated_label="2026-06-08 12:00 UTC")
    # Pinned to the load form so a future change to defer/async/non-defer or
    # a path drift fails the test.
    assert '<script src="/static/dashboard-chart.js" defer></script>' in shell
    # Load order: htmx → Chart.js → dashboard-chart.js (the init depends on
    # both Chart.js and the htmx event seam).
    htmx_idx = shell.index("/static/htmx.min.js")
    chart_idx = shell.index("/static/chart.umd.min.js")
    init_idx = shell.index("/static/dashboard-chart.js")
    assert htmx_idx < chart_idx < init_idx, (
        "shell script tag order must be htmx → chart.umd → dashboard-chart "
        "so 'defer' guarantees Chart and htmx are both defined when the "
        "init script's IIFE runs"
    )
    # The trio sits in the <head>, before the inline <style> block — the
    # render order matches the existing chartjs shell guard above.
    style_idx = shell.index("<style>")
    assert init_idx < style_idx


@pytest.mark.regression
def test_render_per_turn_cost_chart_panel_payload_carries_per_event_uncosted_flag(
    pricing: PricingTable,
) -> None:
    """Arch F1 fold (REV-20260608-025749) — payload distinguishes priced \\$0 from uncosted.

    Before this fold the chart payload's ``cost: 0.0`` collapsed two distinct
    states: a priced cheap turn (the model was on a known tier and the cost
    happened to be 0.0) and an uncosted turn (the model tier was unknown so
    the renderer held the cost back from totals). The collision made it
    impossible for the Phase 2 init script to mark uncosted turns distinctly
    without re-deriving the state from somewhere else. The fold threads
    ``LiveCostEvent.uncosted`` through ``_apply_message`` and onto every
    payload point as a per-entry boolean.

    The end-to-end pin: fold a priced opus turn + an unknown-tier turn, then
    parse the chart payload and assert each entry carries the right flag.
    """
    state = fold_events(
        [
            _msg_event(0, "main", "claude-opus-4-7", input_tokens=1000, output_tokens=500),
            _msg_event(30, "main", "claude-mystery-9", input_tokens=500, output_tokens=200),
        ],
        pricing,
    )
    panel = _render_per_turn_cost_chart_panel(state.recent_events)
    start_marker = 'id="per-turn-cost-data" type="application/json">'
    start = panel.index(start_marker) + len(start_marker)
    end = panel.index("</script>", start)
    points = json.loads(panel[start:end].replace("<\\/", "</"))
    assert len(points) == 2
    # Priced turn: cost > 0, uncosted=False.
    assert points[0]["cost"] == pytest.approx(0.0525)
    assert points[0]["uncosted"] is False
    # Unknown-tier turn: cost = 0.0, uncosted=True. The chart can now render
    # this distinctly (dashed line / different marker) — pre-fold it would
    # have looked indistinguishable from a priced 0.0.
    assert points[1]["cost"] == 0.0
    assert points[1]["uncosted"] is True


# --------------------------------------------------------------------------- #
# Phase 3 Unit 2 — config-drift detector + panel + integration
# --------------------------------------------------------------------------- #


def _pricing_with(last_updated: str = "") -> PricingTable:
    data = dict(PRICING_DATA)
    if last_updated:
        data["last_updated"] = last_updated
    return parse_pricing(data)


def test_drift_kinds_and_hints_are_symmetric() -> None:
    """A drift kind without a hint (or vice versa) is a programmer error.

    Mirrors the failures taxonomy's symmetric-key invariant — the renderer
    looks up :data:`DRIFT_REMEDIATION_HINTS[kind]` with no ``.get()`` fallback
    so a missing entry surfaces as a loud ``KeyError`` rather than a silent
    blank hint row.
    """
    assert set(DRIFT_KINDS) == set(DRIFT_REMEDIATION_HINTS)
    # Each hint is non-empty (a blank hint would defeat the gatekeeper-triage
    # value of the panel).
    for kind in DRIFT_KINDS:
        assert DRIFT_REMEDIATION_HINTS[kind].strip()


def test_pricing_table_carries_last_updated_from_yaml() -> None:
    """``last_updated`` round-trips through :func:`parse_pricing`."""
    table = parse_pricing({**PRICING_DATA, "last_updated": "2026-05-12"})
    assert table.last_updated == "2026-05-12"


def test_pricing_table_last_updated_defaults_empty_when_absent() -> None:
    """A YAML without a ``last_updated`` key parses to an empty string.

    The empty-string default is the typed honest-absence path: the drift
    detector's :func:`detect_stale_pricing_drift` treats it as
    "cannot determine" and emits no signal (rather than fabricating one).
    """
    assert parse_pricing(PRICING_DATA).last_updated == ""


def test_pricing_table_last_updated_accepts_yaml_date_scalar() -> None:
    """An unquoted YAML date scalar is normalised to an ISO string.

    Equivalent: ``last_updated: 2026-05-12`` (unquoted) and
    ``last_updated: "2026-05-12"`` (quoted) yield the same field value, so
    the drift detector's single-shape parser is the only date-handling seam.
    """
    from datetime import date as _date

    table = parse_pricing({**PRICING_DATA, "last_updated": _date(2026, 5, 12)})
    assert table.last_updated == "2026-05-12"


def test_detect_unknown_model_drift_flags_unresolvable_ids(
    pricing: PricingTable,
) -> None:
    """Captured ids the current pricing cannot resolve get one signal each."""
    # "claude-opus-4-7" resolves via the models map.
    # "claude-opus-4" substring-matches "opus".
    # "gpt-4o" resolves to nothing → flagged.
    # "ada-002" resolves to nothing → flagged.
    signals = detect_unknown_model_drift(
        ["claude-opus-4-7", "claude-opus-4", "gpt-4o", "ada-002"], pricing
    )
    observed = [s.observed for s in signals]
    assert observed == ["gpt-4o", "ada-002"]
    assert all(s.kind == UNKNOWN_MODEL for s in signals)


def test_detect_unknown_model_drift_dedups_repeated_ids(pricing: PricingTable) -> None:
    """A duplicate id in the input list yields exactly one signal."""
    signals = detect_unknown_model_drift(["gpt-4o", "gpt-4o", "gpt-4o"], pricing)
    assert len(signals) == 1
    assert signals[0].observed == "gpt-4o"


def test_detect_unknown_model_drift_ignores_unknown_tier_sentinel(
    pricing: PricingTable,
) -> None:
    """The ``UNKNOWN_TIER`` sentinel is not a captured id; it is never flagged.

    The cost path uses ``UNKNOWN_TIER`` as a placeholder for rows with no
    captured model id. Flagging it as drift would imply the YAML is missing
    a resolution for "unknown" — which is incoherent. The detector skips it.
    """
    signals = detect_unknown_model_drift([UNKNOWN_TIER, "claude-opus-4-7"], pricing)
    assert signals == []


def test_detect_unknown_model_drift_ignores_non_string_inputs(
    pricing: PricingTable,
) -> None:
    """Defensive: non-string items in the input (e.g. ``None``) are skipped."""
    signals = detect_unknown_model_drift([None, 42, "gpt-4o"], pricing)  # type: ignore[list-item]
    assert [s.observed for s in signals] == ["gpt-4o"]


def test_detect_stale_pricing_drift_fires_when_pricing_after_earliest() -> None:
    """Pricing updated after the earliest discussion yields one signal."""
    pricing = _pricing_with(last_updated="2026-05-12")
    earliest = datetime(2026, 1, 1, tzinfo=UTC)
    signals = detect_stale_pricing_drift(pricing, earliest)
    assert len(signals) == 1
    s = signals[0]
    assert s.kind == STALE_PRICING
    assert s.observed == "2026-05-12"
    assert "2026-05-12" in s.detail
    assert "2026-01-01" in s.detail


def test_detect_stale_pricing_drift_silent_when_pricing_on_or_before_earliest() -> None:
    """No drift when the pricing date is ON or BEFORE the earliest discussion."""
    pricing = _pricing_with(last_updated="2026-01-01")
    earliest = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    # ON-the-same-date is not drift (boundary inclusive on the no-drift side).
    assert detect_stale_pricing_drift(pricing, earliest) == []
    # BEFORE is also not drift.
    earlier_pricing = _pricing_with(last_updated="2025-12-31")
    assert detect_stale_pricing_drift(earlier_pricing, earliest) == []


def test_detect_stale_pricing_drift_silent_when_last_updated_missing() -> None:
    """An empty ``last_updated`` is honest absence — no fabricated signal."""
    pricing = _pricing_with(last_updated="")
    earliest = datetime(2026, 5, 12, tzinfo=UTC)
    assert detect_stale_pricing_drift(pricing, earliest) == []


def test_detect_stale_pricing_drift_silent_when_last_updated_malformed() -> None:
    """A malformed ``last_updated`` is honest absence too — never crashes."""
    pricing = _pricing_with(last_updated="not-a-date")
    earliest = datetime(2026, 5, 12, tzinfo=UTC)
    assert detect_stale_pricing_drift(pricing, earliest) == []


def test_detect_stale_pricing_drift_silent_when_no_corpus() -> None:
    """No discussions captured → no window to compare against → no signal."""
    pricing = _pricing_with(last_updated="2026-05-12")
    assert detect_stale_pricing_drift(pricing, None) == []


def test_detect_stale_subscription_drift_fires_when_fee_after_earliest() -> None:
    """Subscription fee effective after the earliest discussion yields one signal."""
    fee = SubscriptionFee(monthly_fee_usd=20.0, effective_date="2026-04-01")
    earliest = datetime(2026, 1, 1, tzinfo=UTC)
    signals = detect_stale_subscription_drift(fee, earliest)
    assert len(signals) == 1
    s = signals[0]
    assert s.kind == STALE_SUBSCRIPTION_FEE
    assert s.observed == "2026-04-01"


def test_detect_stale_subscription_drift_silent_when_fee_absent() -> None:
    """No fee configured → no signal (honest absence, never a fabricated drift)."""
    earliest = datetime(2026, 1, 1, tzinfo=UTC)
    assert detect_stale_subscription_drift(None, earliest) == []


def test_detect_stale_subscription_drift_silent_when_effective_date_missing() -> None:
    """A fee with no effective date is honest absence — no signal."""
    fee = SubscriptionFee(monthly_fee_usd=20.0, effective_date="")
    earliest = datetime(2026, 1, 1, tzinfo=UTC)
    assert detect_stale_subscription_drift(fee, earliest) == []


def test_detect_config_drift_merges_all_kinds_in_canonical_order(
    pricing: PricingTable,
) -> None:
    """``detect_config_drift`` returns signals in :data:`DRIFT_KINDS` order."""
    pricing_with_date = _pricing_with(last_updated="2026-05-12")
    fee = SubscriptionFee(monthly_fee_usd=20.0, effective_date="2026-04-01")
    earliest = datetime(2026, 1, 1, tzinfo=UTC)
    signals = detect_config_drift(
        model_ids=["gpt-4o"],
        pricing=pricing_with_date,
        fee=fee,
        earliest_discussion_at=earliest,
    )
    kinds = [s.kind for s in signals]
    # Canonical order: UNKNOWN_MODEL → STALE_PRICING → STALE_SUBSCRIPTION_FEE.
    assert kinds == [UNKNOWN_MODEL, STALE_PRICING, STALE_SUBSCRIPTION_FEE]


def test_detect_config_drift_empty_when_everything_clean(pricing: PricingTable) -> None:
    """No drift across any detector → empty list (the GOOD-news path)."""
    fee = SubscriptionFee(monthly_fee_usd=20.0, effective_date="2026-01-01")
    earliest = datetime(2026, 6, 1, tzinfo=UTC)
    pricing_old = _pricing_with(last_updated="2026-01-01")
    signals = detect_config_drift(
        model_ids=["claude-opus-4-7"],
        pricing=pricing_old,
        fee=fee,
        earliest_discussion_at=earliest,
    )
    assert signals == []


# --- Config drift panel render ------------------------------------------- #


def _empty_dashboard_data(**overrides) -> DashboardData:
    """Build a :class:`DashboardData` shell with cost/failures/A3 all at zero.

    Keeps the config-drift panel tests focused on their own field — the other
    panels carry harmless honest-absence states.
    """
    base = DashboardData(
        cost_report=build_cost_report([], parse_pricing(PRICING_DATA)),
        cost_state=STATE_NOT_RUN,
        failures=[],
        failures_state=STATE_NOT_RUN,
        leverage=LeverageResult(
            configured=False,
            total_cost_usd=0.0,
            coverage_pct=0.0,
            monthly_fee_usd=None,
            window_months=None,
            fee_period="monthly",
            leverage_cumulative=None,
            leverage_per_month=None,
            reason="subscription fee not configured",
        ),
        attribution=DivergenceResult(
            available=False,
            our_cost_usd=0.0,
            independent_cost_usd=None,
            delta_usd=None,
            divergence_pct=None,
            direction=None,
            flaw_class=None,
            scope_coverage_pct=None,
            source_label=None,
            reason="no independent estimate available",
        ),
        pricing_check=DivergenceResult(
            available=False,
            our_cost_usd=0.0,
            independent_cost_usd=None,
            delta_usd=None,
            divergence_pct=None,
            direction=None,
            flaw_class=None,
            scope_coverage_pct=None,
            source_label="otel",
            reason="no independent estimate available",
        ),
    )
    # ``replace`` is the dataclass-safe way to override fields.
    from dataclasses import replace

    return replace(base, **overrides)


def test_render_dashboard_html_includes_config_drift_panel() -> None:
    """The config-drift panel is composed into the static HTML alongside the others."""
    data = _empty_dashboard_data()
    out = render_dashboard_html(data)
    assert "<h3>Config drift</h3>" in out


def test_config_drift_panel_renders_absence_when_no_corpus() -> None:
    """``config_drift_state=not_run`` renders the honest-absence tile."""
    data = _empty_dashboard_data()  # default state is not_run
    out = render_dashboard_html(data)
    # Heading is present; the absence-tile signature ``data-state="absent"`` is
    # present alongside the absence-copy sentence.
    assert "<h3>Config drift</h3>" in out
    assert "No corpus to compare against yet." in out


def test_config_drift_panel_renders_true_zero_data_tile() -> None:
    """``config_drift_state=data`` with no signals = true-zero good-news tile."""
    data = _empty_dashboard_data(config_drift=(), config_drift_state=STATE_DATA)
    out = render_dashboard_html(data)
    assert "No drift detected" in out
    # Spec R3a: a true zero uses ``data-state="data"``, NOT ``absent``.
    drift_panel_start = out.index("<h3>Config drift</h3>")
    drift_panel_slice = out[drift_panel_start : drift_panel_start + 400]
    assert 'data-state="data"' in drift_panel_slice


def test_config_drift_panel_renders_grouped_rows_in_canonical_order() -> None:
    """A panel with all three drift kinds groups them in :data:`DRIFT_KINDS` order."""
    signals = (
        ConfigDriftSignal(kind=UNKNOWN_MODEL, observed="gpt-4o", detail="..."),
        ConfigDriftSignal(kind=STALE_PRICING, observed="2026-05-12", detail="..."),
        ConfigDriftSignal(kind=STALE_SUBSCRIPTION_FEE, observed="2026-04-01", detail="..."),
    )
    data = _empty_dashboard_data(config_drift=signals, config_drift_state=STATE_DATA)
    out = render_dashboard_html(data)
    # Each kind renders as its own group with the ``data-drift-kind`` attr.
    unknown_idx = out.index('data-drift-kind="unknown_model"')
    pricing_idx = out.index('data-drift-kind="stale_pricing"')
    fee_idx = out.index('data-drift-kind="stale_subscription_fee"')
    assert unknown_idx < pricing_idx < fee_idx
    # Each remediation hint appears in escaped form (the renderer routes every
    # dynamic string through ``_esc`` which uses ``html.escape(..., quote=True)``,
    # so apostrophes/quotes inside hints become character entities).
    import html as _html

    for kind in (UNKNOWN_MODEL, STALE_PRICING, STALE_SUBSCRIPTION_FEE):
        assert _html.escape(DRIFT_REMEDIATION_HINTS[kind], quote=True) in out


def test_config_drift_panel_escapes_observed_and_detail() -> None:
    """A drift row's dynamic strings are HTML-escaped at the render boundary."""
    signals = (
        ConfigDriftSignal(
            kind=UNKNOWN_MODEL,
            observed="<script>alert(1)</script>",
            detail="<img src=x onerror=alert(1)>",
        ),
    )
    data = _empty_dashboard_data(config_drift=signals, config_drift_state=STATE_DATA)
    out = render_dashboard_html(data)
    assert "<script>alert(1)</script>" not in out
    assert "<img src=x onerror=alert(1)>" not in out
    # The escaped forms ARE present.
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in out


def test_console_summary_reports_config_drift_count() -> None:
    """The ASCII console summary carries a config-drift line (3 states)."""
    not_run = _empty_dashboard_data()
    lines_not_run = render_console_summary(not_run, output_path="/tmp/x.html")
    assert any("Config drift: not yet checked" in line for line in lines_not_run)

    zero = _empty_dashboard_data(config_drift=(), config_drift_state=STATE_DATA)
    lines_zero = render_console_summary(zero, output_path="/tmp/x.html")
    assert any("Config drift: none detected" in line for line in lines_zero)

    one = _empty_dashboard_data(
        config_drift=(ConfigDriftSignal(kind=UNKNOWN_MODEL, observed="gpt-4o", detail="..."),),
        config_drift_state=STATE_DATA,
    )
    lines_one = render_console_summary(one, output_path="/tmp/x.html")
    assert any("Config drift: 1 row(s) detected" in line for line in lines_one)


# --- assemble_dashboard_data integration --------------------------------- #


@pytest.mark.regression
def test_assemble_dashboard_data_populates_config_drift_from_db(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integration: drift detectors see the captured corpus through the transport.

    Builds a tiny DB with one discussion whose ``created_at`` is BEFORE the
    pricing YAML's ``last_updated``, plus one captured ``model_id`` the
    pricing config does not resolve. The assembler must populate
    :attr:`DashboardData.config_drift` with both signals.
    """
    db_path = _make_db(tmp_path)
    _insert_discussion(db_path, "d1", "2026-01-01 00:00:00", "2026-01-02 00:00:00")
    # One captured row with an unresolved model id.
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """INSERT INTO discussion_model_tokens
               (discussion_id, model_id, tier, tokens_in, tokens_out,
                cache_read_tokens, cache_create_tokens, message_count,
                computed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "d1",
                "gpt-4o",
                UNKNOWN_TIER,
                100,
                100,
                0,
                0,
                1,
                "2026-01-02 00:00:00",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    # Pricing table whose last_updated is AFTER the discussion's created_at.
    pricing = _pricing_with(last_updated="2026-05-12")

    # Subscription fee config: a temp YAML so the drift detector also fires
    # the STALE_SUBSCRIPTION_FEE signal (effective_date after the discussion).
    sub_path = tmp_path / "subscription.yaml"
    sub_path.write_text("monthly_fee_usd: 20.0\neffective_date: '2026-04-01'\n", encoding="utf-8")

    data = dash.assemble_dashboard_data(
        db_path,
        pricing=pricing,
        subscription_path=sub_path,
        otel_path=tmp_path / "otel-does-not-exist.jsonl",
        project_root=tmp_path,
    )
    assert data.config_drift_state == STATE_DATA
    kinds = [s.kind for s in data.config_drift]
    assert UNKNOWN_MODEL in kinds
    assert STALE_PRICING in kinds
    assert STALE_SUBSCRIPTION_FEE in kinds
    # Renderer composes the panel without crashing.
    assert "<h3>Config drift</h3>" in render_dashboard_html(data)


@pytest.mark.regression
def test_assemble_dashboard_data_config_drift_state_not_run_on_empty_db(
    tmp_path: Path,
) -> None:
    """An empty discussions table → ``config_drift_state=not_run`` (honest absence)."""
    db_path = _make_db(tmp_path)
    data = dash.assemble_dashboard_data(
        db_path,
        pricing=parse_pricing(PRICING_DATA),
        subscription_path=tmp_path / "missing-fee.yaml",
        otel_path=tmp_path / "missing-otel.jsonl",
        project_root=tmp_path,
    )
    assert data.config_drift_state == STATE_NOT_RUN
    assert data.config_drift == ()


# --- REV-20260609-060229 in-session folds ---------------------------------- #


def test_detect_stale_subscription_drift_silent_when_no_corpus() -> None:
    """qa F1 fold: symmetric no-corpus test (pricing path has one already).

    A fee with a usable effective_date but no discussions captured yields no
    signal — the window-to-compare-against does not yet exist, so the typed
    honest-absence path fires.
    """
    fee = SubscriptionFee(monthly_fee_usd=20.0, effective_date="2026-04-01")
    assert detect_stale_subscription_drift(fee, None) == []


def test_detect_stale_subscription_drift_silent_when_effective_date_malformed() -> None:
    """qa F5 fold: malformed effective_date is honest absence (no signal).

    Symmetric to ``test_detect_stale_pricing_drift_silent_when_last_updated_malformed``
    — routes through ``_parse_iso_date`` returning ``None``.
    """
    fee = SubscriptionFee(monthly_fee_usd=20.0, effective_date="not-a-date")
    earliest = datetime(2026, 1, 1, tzinfo=UTC)
    assert detect_stale_subscription_drift(fee, earliest) == []


def test_pricing_table_last_updated_explicit_empty_string() -> None:
    """qa F4 fold: an explicit ``last_updated: ""`` YAML key parses to "".

    The ``_pricing_with("")`` test helper skips the assignment for the
    empty-string case (so the YAML key is absent rather than present-but-blank).
    This test pins the explicit-empty-string YAML input path independently of
    the helper's key-omission shortcut — if ``parse_pricing`` ever distinguishes
    absence from empty-string, both paths stay covered.
    """
    table = parse_pricing({**PRICING_DATA, "last_updated": ""})
    assert table.last_updated == ""


def test_parse_subscription_fee_date_scalar_normalised_to_iso_string() -> None:
    """qa F7 fold: PyYAML unquoted ISO date scalar → ISO string on SubscriptionFee.

    Symmetric to ``test_pricing_table_last_updated_accepts_yaml_date_scalar``.
    The drift detector's single-shape ``_parse_iso_date`` is the only date
    handler downstream; this test pins that both YAML inputs
    (``effective_date: '2026-04-01'`` quoted and ``effective_date: 2026-04-01``
    unquoted) yield the same string value here.
    """
    from datetime import date as _date

    fee = parse_subscription_fee({"monthly_fee_usd": 20.0, "effective_date": _date(2026, 4, 1)})
    assert fee is not None
    assert fee.effective_date == "2026-04-01"


@pytest.mark.regression
def test_load_drift_inputs_schema_pins_not_null_created_at(tmp_path: Path) -> None:
    """qa F1 fold: the ``discussions.created_at NOT NULL`` constraint is the
    invariant ``load_drift_inputs`` relies on to skip a row-count tiebreaker.

    The earlier draft of ``load_drift_inputs`` had a defensive
    ``SELECT COUNT(*)`` branch to distinguish "empty table" from
    "all-NULL column". The schema makes the all-NULL case unreachable, so
    the branch is genuine dead code (per principle: do not add error
    handling for scenarios that can't happen). This regression test pins
    the schema invariant — if a future migration drops ``NOT NULL`` on
    ``created_at``, this test fires and the dead-branch reasoning must be
    revisited.
    """
    db_path = _make_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO discussions
                   (discussion_id, created_at, closed_at, risk_level,
                    collaboration_mode, status)
                   VALUES (?, NULL, NULL, 'medium', 'structured-dialogue', 'open')""",
                ("d-null-ts",),
            )
    finally:
        conn.close()


def test_config_drift_panel_absence_action_points_at_capture_flow() -> None:
    """qa F2 + ux F1 CONVERGENT fold: not_run action hint must NOT point at analyze_cost.

    The pre-fold copy said "Run scripts/telemetry/analyze_cost.py after capturing
    a session" — but analyze_cost.py reads the discussions table; it does not
    populate it. A user following that hint would loop. This test pins that the
    action hint references the capture pipeline (framework commands), not the
    cost analyzer. Calls the panel renderer directly so the assertion is scoped
    to the Config drift tile (the dashboard's other panels also reference
    analyze_cost.py in their own absence copy).
    """
    from src.telemetry.dashboard import _render_config_drift_panel

    data = _empty_dashboard_data()  # default state is not_run
    panel = _render_config_drift_panel(data)
    # The wrong target is GONE from this panel.
    assert "analyze_cost.py" not in panel
    # The capture-flow framing is present (at least one framework command
    # appears in the action hint).
    assert "/plan" in panel or "/review" in panel


def test_render_dashboard_html_config_drift_group_label_uses_static_map() -> None:
    """ux F4 fold: kind headers come from _DRIFT_KIND_LABEL, not str.replace.capitalize.

    The pre-fold renderer derived headers from ``kind.replace("_", " ").capitalize()``
    yielding "Unknown model". The fold replaces that with manager-facing labels
    that name the consequence ("Unpriced model id"). This test pins the new
    label vocabulary so a future regression that re-introduced the derivation
    fails here.
    """
    signals = (
        ConfigDriftSignal(kind=UNKNOWN_MODEL, observed="gpt-4o", detail="x"),
        ConfigDriftSignal(kind=STALE_PRICING, observed="2026-05-12", detail="x"),
        ConfigDriftSignal(kind=STALE_SUBSCRIPTION_FEE, observed="2026-04-01", detail="x"),
    )
    data = _empty_dashboard_data(config_drift=signals, config_drift_state=STATE_DATA)
    out = render_dashboard_html(data)
    assert "Unpriced model id" in out
    assert "Stale pricing config" in out
    assert "Stale subscription fee" in out
    # The pre-fold derivation result for UNKNOWN_MODEL is absent.
    assert "Unknown model" not in out
