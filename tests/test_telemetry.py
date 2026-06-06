"""Tests for telemetry Layer A1 — per-tier cost + coverage.

Pure-logic tests (pricing resolution, cost aggregation, coverage denominator)
plus integration tests for the analyzer that NEVER touch the live ~/.claude
directory — the transcript root and project root are monkeypatched onto the
reused ``ingest_token_usage`` module and the DB path is a ``tmp_path`` SQLite.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from scripts import ingest_token_usage as itu
from scripts.init_db import init_db
from scripts.telemetry import analyze_cost as ac
from src.telemetry.cost import ModelTokenRow, build_cost_report
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
