"""Tests for scripts/telemetry/call_log.py + the cache-read ratio math.

SPEC-20260716-093231 (cost/cache instrument, wave 1). Read side uses fake
transcripts under a monkeypatched projects root; write side (JSONL + DB)
targets tmp_path via the module-level constants (R7 write-side isolation) —
no test touches live ``~/.claude`` or the real ``metrics/`` files.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import ingest_token_usage as itu  # noqa: E402
from scripts.init_db import init_db  # noqa: E402
from scripts.telemetry import call_log  # noqa: E402
from src.telemetry.cost import (  # noqa: E402
    ModelTokenRow,
    TierCost,
    build_cost_report,
    compute_cache_read_ratio,
)
from src.telemetry.pricing import parse_pricing  # noqa: E402

TS1 = "2026-07-16T10:00:00Z"
TS2 = "2026-07-16T10:05:00Z"
TS3 = "2026-07-16T10:10:00Z"

PRICING_DATA = {
    "tiers": {
        "opus": {
            "input": 15.0,
            "output": 75.0,
            "cache_read_multiplier": 0.1,
            "cache_create_multiplier": 1.25,
        },
    },
    "models": {"claude-opus-4-7": "opus"},
}


def _msg_line(
    message_id: str,
    timestamp: str,
    model: str | None = "claude-opus-4-7",
    *,
    usage: dict | None = None,
) -> str:
    """Build one transcript JSONL line; pass ``usage`` explicitly to omit keys."""
    message: dict = {"id": message_id}
    if model is not None:
        message["model"] = model
    message["usage"] = (
        usage
        if usage is not None
        else {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_input_tokens": 300,
            "cache_creation_input_tokens": 100,
        }
    )
    return json.dumps({"timestamp": timestamp, "message": message})


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Isolated transcript root + project root + DB + JSONL output."""
    projects_root = tmp_path / "claude_projects"
    projects_root.mkdir()
    project_root = tmp_path / "proj"
    project_root.mkdir()
    db_path = tmp_path / "evaluation.db"
    init_db(db_path)
    log_path = tmp_path / "model_call_log.jsonl"
    monkeypatch.setattr(itu, "CLAUDE_PROJECTS_ROOT", projects_root)
    monkeypatch.setattr(itu, "PROJECT_ROOT", project_root)
    # Write-side isolation via the module-level constants (spec R7).
    monkeypatch.setattr(call_log, "DB_PATH", db_path)
    monkeypatch.setattr(call_log, "LOG_PATH", log_path)

    class Env:
        pass

    e = Env()
    e.projects_root = projects_root
    e.project_root = project_root
    e.db_path = db_path
    e.log_path = log_path
    e.session_dir = projects_root / itu._project_slug(project_root)
    return e


def _write_main_session(env, lines: list[str], name: str = "session1.jsonl") -> Path:
    env.session_dir.mkdir(parents=True, exist_ok=True)
    target = env.session_dir / name
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def _write_dir_session(
    env, main_lines: list[str], subagent_lines: list[str], name: str = "sess-dir"
) -> Path:
    session = env.session_dir / name
    (session / "subagents").mkdir(parents=True, exist_ok=True)
    (session / f"{name}.jsonl").write_text("\n".join(main_lines) + "\n", encoding="utf-8")
    (session / "subagents" / "agent-1.jsonl").write_text(
        "\n".join(subagent_lines) + "\n", encoding="utf-8"
    )
    return session


def _read_log(env) -> list[dict]:
    lines = env.log_path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _read_state(env) -> dict:
    conn = sqlite3.connect(str(env.db_path))
    try:
        row = conn.execute(
            "SELECT value FROM telemetry_run_state WHERE key = ?",
            (call_log.WATERMARK_KEY,),
        ).fetchone()
    finally:
        conn.close()
    return json.loads(row[0]) if row and row[0] else {}


# --------------------------------------------------------------------------- #
# compute_cache_read_ratio — pure (AC3)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("tokens_in", "cache_read", "cache_create", "expected"),
    [
        (100, 300, 100, 0.6),  # normal
        (100, 0, 0, 0.0),  # known-zero cache read is a real 0.0, not absence
        (0, 0, 0, None),  # zero denominator -> honest None
        (None, 5, 0, None),  # unknown component is never treated as 0
        (5, None, 0, None),
        (5, 0, None, None),
    ],
)
def test_compute_cache_read_ratio(tokens_in, cache_read, cache_create, expected):
    result = compute_cache_read_ratio(tokens_in, cache_read, cache_create)
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected)


def test_tier_cost_ratio_property():
    tier = TierCost(tier="opus", tokens_in=100, cache_read_tokens=300, cache_create_tokens=100)
    assert tier.cache_read_ratio == pytest.approx(0.6)
    assert TierCost(tier="empty").cache_read_ratio is None


def test_cost_report_overall_ratio_across_tiers():
    pricing = parse_pricing(PRICING_DATA)
    rows = [
        ModelTokenRow("D1", "claude-opus-4-7", "opus", 100, 50, 300, 100, 1),
        ModelTokenRow("D2", "claude-opus-4-7", "opus", 100, 50, 100, 100, 1),
    ]
    report = build_cost_report(rows, pricing)
    # (300+100) / (200 + 400 + 200)
    assert report.cache_read_ratio == pytest.approx(400 / 800)
    assert build_cost_report([], pricing).cache_read_ratio is None


# --------------------------------------------------------------------------- #
# Emitter — AC1/AC2/AC3 line-level
# --------------------------------------------------------------------------- #


def test_ac1_one_line_per_message_with_fields_and_source_kind(env):
    _write_dir_session(
        env,
        main_lines=[_msg_line("msg_main", TS1)],
        subagent_lines=[_msg_line("msg_sub", TS2)],
    )
    summary = call_log.run_call_log()
    assert summary["calls_logged"] == 2
    assert summary["partial"] is False
    by_id = {entry["message_id"]: entry for entry in _read_log(env)}
    assert set(by_id) == {"msg_main", "msg_sub"}
    main_entry = by_id["msg_main"]
    assert main_entry["source_kind"] == "main"
    assert by_id["msg_sub"]["source_kind"] == "subagent"
    assert main_entry["input_tokens"] == 100
    assert main_entry["cache_read_input_tokens"] == 300
    assert main_entry["cache_creation_input_tokens"] == 100
    assert main_entry["output_tokens"] == 50
    assert main_entry["cache_read_ratio"] == pytest.approx(0.6)
    assert main_entry["model"] == "claude-opus-4-7"
    assert main_entry["session_id"] == "sess-dir"


def test_ac2_second_run_appends_no_duplicates(env):
    _write_main_session(env, [_msg_line("msg_a", TS1), _msg_line("msg_b", TS2)])
    assert call_log.run_call_log()["calls_logged"] == 2
    assert call_log.run_call_log()["calls_logged"] == 0
    entries = _read_log(env)
    assert len(entries) == 2
    assert len({e["message_id"] for e in entries}) == 2


def test_ac2_tie_at_watermark_unseen_id_is_still_logged(env, monkeypatch):
    """A message whose ts EQUALS the stored watermark must be logged when its
    id is unseen — a strict ``>`` selector would silently skip it (the
    analyze_cost/analyze_failures regression class)."""
    monkeypatch.setattr(call_log, "FLUSH_LAG_SECONDS", 0)
    session = _write_main_session(env, [_msg_line("msg_a", TS1)])
    assert call_log.run_call_log()["calls_logged"] == 1
    assert _read_state(env)["ts"] is not None  # watermark == TS1 exactly (lag 0)
    # A new message sharing the exact watermark timestamp arrives late.
    session.write_text(
        "\n".join([_msg_line("msg_a", TS1), _msg_line("msg_b", TS1)]) + "\n",
        encoding="utf-8",
    )
    assert call_log.run_call_log()["calls_logged"] == 1
    entries = _read_log(env)
    assert sorted(e["message_id"] for e in entries) == ["msg_a", "msg_b"]


def test_ac3_ratio_null_in_line_for_zero_and_unknown(env):
    _write_main_session(
        env,
        [
            _msg_line(
                "msg_zero",
                TS1,
                usage={
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                },
            ),
            # input_tokens missing entirely: unknown component -> ratio null,
            # never computed by treating the missing component as 0.
            _msg_line(
                "msg_unknown",
                TS2,
                usage={"cache_read_input_tokens": 5, "cache_creation_input_tokens": 0},
            ),
        ],
    )
    call_log.run_call_log()
    by_id = {e["message_id"]: e for e in _read_log(env)}
    assert by_id["msg_zero"]["cache_read_ratio"] is None
    assert by_id["msg_unknown"]["cache_read_ratio"] is None
    assert by_id["msg_unknown"]["input_tokens"] is None  # honest unknown


# --------------------------------------------------------------------------- #
# Partial pass / cooperative deadline (AC6i) + state contracts
# --------------------------------------------------------------------------- #


def test_partial_pass_scans_first_file_only_and_keeps_watermark(env, monkeypatch):
    """Fake clock jumps past the deadline after the first session path: the
    pass stops (1 of 2 files), the watermark is NOT advanced, and the next
    full pass picks up the remainder with no duplicates."""
    _write_main_session(env, [_msg_line("msg_a", TS1)], name="a.jsonl")
    _write_main_session(env, [_msg_line("msg_b", TS2)], name="b.jsonl")

    seq = [0.0, 0.0, 0.0, 20.0, 20.0]
    counter = {"n": 0}

    def fake_time() -> float:
        index = min(counter["n"], len(seq) - 1)
        counter["n"] += 1
        return seq[index]

    monkeypatch.setattr(call_log.time, "time", fake_time)
    summary = call_log.run_call_log(budget_seconds=10)
    assert summary["partial"] is True
    assert summary["calls_logged"] == 1
    assert summary["watermark"] is None  # never advanced on a partial pass
    state = _read_state(env)
    assert state["ts"] is None
    assert len(state["ids"]) == 1  # logged id merged so it cannot re-log

    # Full pass completes the corpus with zero duplicates.
    summary2 = call_log.run_call_log()
    assert summary2["partial"] is False
    assert summary2["calls_logged"] == 1
    entries = _read_log(env)
    assert sorted(e["message_id"] for e in entries) == ["msg_a", "msg_b"]


def test_corrupt_state_degrades_to_full_relog_once(env):
    """Documented contract (accepted at checkpoint): corrupt dedup state means
    one full re-log — duplicate lines, never silent loss. Readers dedup by
    message_id."""
    _write_main_session(env, [_msg_line("msg_a", TS1), _msg_line("msg_b", TS2)])
    assert call_log.run_call_log()["calls_logged"] == 2
    conn = sqlite3.connect(str(env.db_path))
    try:
        conn.execute(
            "UPDATE telemetry_run_state SET value = ? WHERE key = ?",
            ("{not json", call_log.WATERMARK_KEY),
        )
        conn.commit()
    finally:
        conn.close()
    assert call_log.run_call_log()["calls_logged"] == 2  # re-logged once
    entries = _read_log(env)
    assert len(entries) == 4
    # State is healed: a third run appends nothing.
    assert call_log.run_call_log()["calls_logged"] == 0


def test_deleting_log_does_not_rebuild_it(env):
    """Dedup state lives in the DB: deleting the JSONL reclaims disk but the
    emitter does NOT repopulate it (documented operator gotcha)."""
    _write_main_session(env, [_msg_line("msg_a", TS1)])
    assert call_log.run_call_log()["calls_logged"] == 1
    env.log_path.unlink()
    assert call_log.run_call_log()["calls_logged"] == 0
    assert not env.log_path.exists()


def test_ac12_truncated_trailing_line_is_healed(env):
    _write_main_session(env, [_msg_line("msg_a", TS1)])
    env.log_path.write_text(
        '{"ts": "2026-07-16T09:00:00+00:00", "message_id": "msg_ol', encoding="utf-8"
    )
    assert call_log.run_call_log()["calls_logged"] == 1
    raw_lines = env.log_path.read_text(encoding="utf-8").splitlines()
    assert len(raw_lines) == 2  # fragment, then the healed append on its own line
    parsed = json.loads(raw_lines[1])  # every post-fragment line parses cleanly
    assert parsed["message_id"] == "msg_a"


def test_late_flushed_file_beyond_lag_window_is_dropped(env):
    """Documented 4th accepted bound (review qa F2): a transcript file that
    materializes only after the watermark has advanced past its timestamps is
    permanently skipped — silent loss accepted beyond FLUSH_LAG_SECONDS."""
    _write_main_session(env, [_msg_line("msg_now", "2026-07-16T10:00:00Z")], name="a.jsonl")
    assert call_log.run_call_log()["calls_logged"] == 1  # watermark -> 09:50
    # A file flushed late, with timestamps older than the watermark.
    _write_main_session(env, [_msg_line("msg_late", "2026-07-16T09:45:00Z")], name="b.jsonl")
    assert call_log.run_call_log()["calls_logged"] == 0
    assert sorted(e["message_id"] for e in _read_log(env)) == ["msg_now"]


def test_missing_projects_root_is_a_clean_noop(env, monkeypatch, tmp_path):
    _write_main_session(env, [_msg_line("msg_a", TS1)])
    monkeypatch.setattr(itu, "CLAUDE_PROJECTS_ROOT", tmp_path / "nowhere")
    summary = call_log.run_call_log()
    assert summary["calls_logged"] == 0
    assert not env.log_path.exists()


def test_no_sessions_is_a_clean_noop(env):
    # env creates the projects root but no session dir for the project slug.
    summary = call_log.run_call_log()
    assert summary["calls_logged"] == 0
    assert summary["partial"] is False
    assert not env.log_path.exists()


def test_same_message_id_across_two_session_paths_logs_once(env):
    _write_main_session(env, [_msg_line("msg_shared", TS1)], name="a.jsonl")
    _write_main_session(env, [_msg_line("msg_shared", TS1)], name="b.jsonl")
    assert call_log.run_call_log()["calls_logged"] == 1
    assert [e["message_id"] for e in _read_log(env)] == ["msg_shared"]


def test_ac7_session_path_outside_projects_root_is_skipped(env, monkeypatch, tmp_path):
    outside = tmp_path / "outside_dir"
    outside.mkdir()
    (outside / "evil.jsonl").write_text(_msg_line("msg_evil", TS1) + "\n", encoding="utf-8")
    monkeypatch.setattr(itu, "discover_session_dirs", lambda root: [outside])
    assert call_log.run_call_log()["calls_logged"] == 0
    assert not env.log_path.exists()


def test_missing_db_is_a_clean_noop(env, monkeypatch, tmp_path):
    _write_main_session(env, [_msg_line("msg_a", TS1)])
    monkeypatch.setattr(call_log, "DB_PATH", tmp_path / "nope" / "missing.db")
    summary = call_log.run_call_log()
    assert summary["calls_logged"] == 0
    assert not env.log_path.exists()


@pytest.mark.regression
def test_parse_message_line_two_arg_positional_compat():
    """src/context_sensor.py calls _parse_message_line(line, path) positionally;
    the source_kind addition must stay a defaulted third parameter."""
    record = itu._parse_message_line(_msg_line("msg_x", TS1), Path("x.jsonl"))
    assert record is not None
    assert record.source_kind == "main"


# --------------------------------------------------------------------------- #
# CLI surface — AC8 (ASCII) + stdout/stderr routing (AC11 defense in depth)
# --------------------------------------------------------------------------- #


def test_cli_summary_stdout_and_ascii(env, monkeypatch, capsys):
    _write_main_session(env, [_msg_line("msg_a", TS1)])
    monkeypatch.setattr(sys, "argv", ["call_log.py"])
    call_log.main()
    captured = capsys.readouterr()
    assert captured.out.startswith("call-log: 1 call(s) logged")
    assert captured.err == ""
    captured.out.encode("ascii")
    captured.out.encode("cp1252")


def test_cli_from_hook_routes_summary_to_stderr(env, monkeypatch, capsys):
    _write_main_session(env, [_msg_line("msg_a", TS1)])
    monkeypatch.setattr(sys, "argv", ["call_log.py", "--from-hook"])
    call_log.main()
    captured = capsys.readouterr()
    assert captured.out == ""  # stdout stays silent for the hook (AC11)
    assert captured.err.startswith("call-log:")
    captured.err.encode("ascii")


def test_gitignore_covers_the_log_ac9():
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "metrics/model_call_log.jsonl" in gitignore.splitlines()
