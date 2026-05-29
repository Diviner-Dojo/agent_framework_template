"""Tests for src/context_sensor.py (ADR-0018, model-aware session wrap-up).

Covers the threshold model (min(fraction*window, abs_cap) + conservative floor),
statusLine parsing + graceful degrade, session-id allowlisting, sidecar
read/write + freshness boundary, transcript-estimate fallback, the debounced
guard state machine, handoff retention, and the (no-spawn) auto-launch command
builder. Every path is exercised with injected config / state_dir / project_root
so no test touches the real ``~/.claude`` or the system clock.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.ingest_token_usage import MessageRecord
from src.context_sensor import (
    Occupancy,
    ThresholdProfile,
    build_launch_command,
    build_sidecar_record,
    classify_level,
    enforce_retention,
    estimate_from_transcript,
    evaluate_guard,
    is_valid_session_id,
    load_config,
    occupancy_from_statusline,
    process_statusline,
    read_sidecar,
    resolve_threshold,
    sidecar_path,
    write_sidecar_atomic,
)

# ---------------------------------------------------------------------------
# Fixtures / factories.
# ---------------------------------------------------------------------------


def _make_statusline_json(
    *,
    used_percentage: float | None = 14.0,
    window: int | None = 1_000_000,
    total_input_tokens: int | None = None,
    model: object = "claude-opus-4-7",
    session_id: str = "sess-abc_123",
) -> dict:
    """Pin the statusLine JSON shape this feature depends on (B-QA-6).

    Documents the exact fields the sensor reads, with sensible defaults so each
    test overrides only what it cares about.
    """
    cw: dict = {}
    if window is not None:
        cw["context_window_size"] = window
    if used_percentage is not None:
        cw["used_percentage"] = used_percentage
    if total_input_tokens is not None:
        cw["total_input_tokens"] = total_input_tokens
    payload: dict = {"context_window": cw, "session_id": session_id}
    if model is not None:
        payload["model"] = model
    return payload


def _make_record(
    *,
    input_tokens: int | None = 100,
    cache_read_tokens: int | None = 0,
    cache_create_tokens: int | None = 0,
    model: str | None = "claude-opus-4-7",
    ts: datetime | None = None,
) -> MessageRecord:
    """Construct a MessageRecord for transcript-estimate tests."""
    return MessageRecord(
        message_id="msg_x",
        timestamp=ts or datetime(2026, 5, 23, 12, 0, tzinfo=UTC),
        model=model,
        input_tokens=input_tokens,
        output_tokens=10,
        cache_read_tokens=cache_read_tokens,
        cache_create_tokens=cache_create_tokens,
        source_file=Path("fixture.jsonl"),
    )


def _profile(name: str, *, window: int, fraction: float, cap: int) -> dict:
    """Build a single-profile synthetic config keyed by ``name``."""
    return {
        "profiles": {
            name: {
                "context_window": window,
                "soft_wrapup_fraction": fraction,
                "hard_wrapup_fraction": fraction,
                "soft_abs_cap_tokens": cap,
                "hard_abs_cap_tokens": cap,
                "auto_compact_fraction": 0.83,
            }
        },
        "models": {},
        "defaults": {"profile": name},
    }


# A small deterministic config: window 1000 -> soft 100, hard 200.
TINY_CONFIG: dict = {
    "profiles": {
        "tiny": {
            "context_window": 1000,
            "soft_wrapup_fraction": 0.10,
            "hard_wrapup_fraction": 0.20,
            "soft_abs_cap_tokens": 100,
            "hard_abs_cap_tokens": 200,
            "auto_compact_fraction": 0.83,
        }
    },
    "models": {},
    "defaults": {"profile": "tiny"},
    "settings": {
        "sidecar_freshness_seconds": 300,
        "handoff_retention_cap": 5,
        "max_auto_launch_depth": 1,
    },
}


def _write_sidecar(
    state_dir: Path, session_id: str, used_tokens: int, *, model: str = "tiny-model"
) -> None:
    """Write a fresh occupancy sidecar for the guard tests."""
    record = {
        "session_id": session_id,
        "used_tokens": used_tokens,
        "used_percentage": used_tokens / 10.0,
        "window": 1000,
        "model": model,
        "tier": "tiny",
        "soft_tok": 100,
        "hard_tok": 200,
        "source": "statusline",
        "written_at_epoch": time.time(),
    }
    write_sidecar_atomic(record, state_dir)


# ---------------------------------------------------------------------------
# AC-1: threshold resolution — min() crossover + conservative floor.
# ---------------------------------------------------------------------------


class TestResolveThreshold:
    def test_known_opus_uses_absolute_cap(self) -> None:
        prof = resolve_threshold("claude-opus-4-7")
        assert prof.profile_name == "opus_1m"
        assert prof.soft_tok == 140000 and prof.hard_tok == 180000
        assert prof.matched is True

    def test_fraction_governs_when_below_cap(self) -> None:
        # 0.5 * 200000 = 100000 < cap 130000 -> fraction governs.
        prof = resolve_threshold("m", _profile("p", window=200000, fraction=0.5, cap=130000))
        assert prof.soft_tok == 100000

    def test_cap_governs_when_below_fraction(self) -> None:
        # 0.55 * 1_000_000 = 550000 > cap 140000 -> cap governs.
        prof = resolve_threshold("m", _profile("p", window=1_000_000, fraction=0.55, cap=140000))
        assert prof.soft_tok == 140000

    def test_degenerate_fraction_equals_cap(self) -> None:
        # 0.5 * 200000 = 100000 == cap 100000 -> both equal.
        prof = resolve_threshold("m", _profile("p", window=200000, fraction=0.5, cap=100000))
        assert prof.soft_tok == 100000

    def test_unknown_model_falls_back_to_conservative_floor(self) -> None:
        cfg = load_config()
        unknown = resolve_threshold("totally-unknown-xyz", cfg)
        assert unknown.matched is False
        known = ["claude-opus-4-7", "claude-sonnet-4-6", "claude-sonnet-4-5", "claude-haiku-4-5"]
        for model in known:
            prof = resolve_threshold(model, cfg)
            assert unknown.soft_tok <= prof.soft_tok
            assert unknown.hard_tok <= prof.hard_tok

    def test_none_model_falls_back(self) -> None:
        prof = resolve_threshold(None)
        assert prof.matched is False

    def test_missing_config_uses_hardcoded_profile(self) -> None:
        prof = resolve_threshold("anything", {})
        assert prof.soft_tok > 0 and prof.hard_tok > prof.soft_tok


# ---------------------------------------------------------------------------
# AC-2 / AC-2b: statusLine parsing + session-id allowlist.
# ---------------------------------------------------------------------------


class TestOccupancyFromStatusline:
    def test_valid_percentage_payload(self) -> None:
        occ = occupancy_from_statusline(_make_statusline_json(used_percentage=14.0))
        assert occ is not None
        assert occ.used_tokens == 140000
        assert occ.source == "statusline"
        assert occ.model == "claude-opus-4-7"

    def test_total_input_tokens_path(self) -> None:
        occ = occupancy_from_statusline(
            _make_statusline_json(used_percentage=None, total_input_tokens=50000, window=200000)
        )
        assert occ is not None and occ.used_tokens == 50000
        assert occ.used_percentage == pytest.approx(25.0)

    def test_model_as_object(self) -> None:
        payload = _make_statusline_json(model={"id": "claude-sonnet-4-6", "display_name": "x"})
        occ = occupancy_from_statusline(payload)
        assert occ is not None and occ.model == "claude-sonnet-4-6"

    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"context_window": {}},
            {"context_window": {"context_window_size": 200000, "used_percentage": None}},
            {"context_window": {"used_percentage": 50.0}},  # no window
        ],
    )
    def test_missing_fields_degrade_to_none(self, payload: dict) -> None:
        assert occupancy_from_statusline(payload) is None


class TestSessionIdValidation:
    @pytest.mark.parametrize(
        "value",
        ["../../etc/passwd", "", "a" * 65, None, 123, "has space", "semi;colon", "a/b"],
    )
    def test_invalid_ids_rejected(self, value: object) -> None:
        assert is_valid_session_id(value) is False

    @pytest.mark.parametrize("value", ["abc", "Sess-123_x", "A" * 64])
    def test_valid_ids_accepted(self, value: str) -> None:
        assert is_valid_session_id(value) is True

    def test_sidecar_path_none_for_invalid_id(self, tmp_path: Path) -> None:
        assert sidecar_path("../evil", tmp_path) is None

    def test_write_sidecar_rejects_invalid_id(self, tmp_path: Path) -> None:
        assert write_sidecar_atomic({"session_id": "../evil", "used_tokens": 1}, tmp_path) is None


# ---------------------------------------------------------------------------
# AC-3 / AC-3b: transcript fallback + sidecar freshness boundary.
# ---------------------------------------------------------------------------


class TestEstimateFromTranscript:
    def test_records_seam_sums_resident_tokens(self) -> None:
        rec = _make_record(input_tokens=1000, cache_read_tokens=500, cache_create_tokens=200)
        occ = estimate_from_transcript(records=[rec])
        assert occ is not None
        assert occ.used_tokens == 1700
        assert occ.source == "transcript-estimate"

    def test_picks_newest_record(self) -> None:
        old = _make_record(input_tokens=100, ts=datetime(2026, 5, 23, 10, 0, tzinfo=UTC))
        new = _make_record(input_tokens=900, ts=datetime(2026, 5, 23, 12, 0, tzinfo=UTC))
        occ = estimate_from_transcript(records=[old, new])
        assert occ is not None and occ.used_tokens == 900

    def test_empty_records_returns_none(self) -> None:
        assert estimate_from_transcript(records=[]) is None

    def test_all_unusable_records_returns_none(self) -> None:
        rec = _make_record(input_tokens=None, cache_read_tokens=None, cache_create_tokens=None)
        assert estimate_from_transcript(records=[rec]) is None

    def test_unknown_model_uses_conservative_window(self) -> None:
        rec = _make_record(
            input_tokens=500, cache_read_tokens=0, cache_create_tokens=0, model=None
        )
        occ = estimate_from_transcript(records=[rec], config=load_config())
        assert occ is not None
        # Conservative floor profile is the 200K window.
        assert occ.window == 200000

    def test_fixture_file_outside_projects_root_parses(self, tmp_path: Path) -> None:
        # Reuses the parse seam directly, bypassing the projects-root guard.
        line = json.dumps(
            {
                "message": {
                    "id": "msg_1",
                    "model": "claude-opus-4-7",
                    "usage": {"input_tokens": 4242},
                },
                "timestamp": "2026-05-23T12:00:00Z",
            }
        )
        transcript = tmp_path / "session.jsonl"
        transcript.write_text(line + "\n", encoding="utf-8")
        occ = estimate_from_transcript(transcript)
        assert occ is not None and occ.used_tokens == 4242

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        assert estimate_from_transcript(tmp_path / "nope.jsonl") is None


class TestReadSidecarFreshness:
    def _write(self, tmp_path: Path, written_at: float) -> None:
        path = sidecar_path("sess", tmp_path)
        assert path is not None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"used_tokens": 5, "written_at_epoch": written_at}), "utf-8")

    def test_fresh_just_inside_window(self, tmp_path: Path) -> None:
        now = 1_000_000.0
        self._write(tmp_path, now - 300 + 1)
        assert read_sidecar("sess", tmp_path, now=now, freshness_seconds=300) is not None

    def test_stale_just_outside_window(self, tmp_path: Path) -> None:
        now = 1_000_000.0
        self._write(tmp_path, now - 300 - 1)
        assert read_sidecar("sess", tmp_path, now=now, freshness_seconds=300) is None

    def test_exact_boundary_is_fresh(self, tmp_path: Path) -> None:
        now = 1_000_000.0
        self._write(tmp_path, now - 300)  # strict '>' means exactly-at is fresh
        assert read_sidecar("sess", tmp_path, now=now, freshness_seconds=300) is not None

    def test_missing_sidecar_returns_none(self, tmp_path: Path) -> None:
        assert read_sidecar("sess", tmp_path) is None

    def test_corrupt_sidecar_returns_none(self, tmp_path: Path) -> None:
        path = sidecar_path("sess", tmp_path)
        assert path is not None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")
        assert read_sidecar("sess", tmp_path) is None


# ---------------------------------------------------------------------------
# Sidecar round-trip via process_statusline (the writer entry point).
# ---------------------------------------------------------------------------


class TestProcessStatusline:
    def test_writes_sidecar_and_returns_display(self, tmp_path: Path) -> None:
        payload = _make_statusline_json(used_percentage=14.0, session_id="sess1")
        line = process_statusline(payload, state_dir=tmp_path)
        assert "ctx" in line
        path = sidecar_path("sess1", tmp_path)
        assert path is not None and path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["source"] == "statusline"
        assert data["tier"] == "opus_1m"
        assert data["soft_tok"] == 140000 and data["hard_tok"] == 180000

    def test_missing_fields_no_sidecar(self, tmp_path: Path) -> None:
        line = process_statusline({}, state_dir=tmp_path)
        assert line == "ctx ?"
        assert not any(tmp_path.glob("context-occupancy.*.json"))

    def test_warn_marker_above_soft(self, tmp_path: Path) -> None:
        line = process_statusline(_make_statusline_json(used_percentage=20.0), state_dir=tmp_path)
        assert "wrap-up" in line

    @pytest.mark.regression
    def test_display_is_ascii_encodable(self, tmp_path: Path) -> None:
        # Regression: statusLine prints to a raw terminal that may use cp1252;
        # a non-ASCII char (e.g. emoji) crashed the hook with UnicodeEncodeError.
        for pct in (5.0, 20.0, 60.0):
            line = process_statusline(
                _make_statusline_json(used_percentage=pct), state_dir=tmp_path
            )
            line.encode("cp1252")  # must not raise
        process_statusline({}, state_dir=tmp_path).encode("cp1252")


# ---------------------------------------------------------------------------
# AC-4: classify_level boundaries + the debounced guard state machine.
# ---------------------------------------------------------------------------


class TestClassifyLevel:
    @staticmethod
    def _prof() -> ThresholdProfile:
        return ThresholdProfile("p", 1000, 100, 200, 830, "m", True)

    @staticmethod
    def _occ(used: int) -> Occupancy:
        return Occupancy(used, used / 10.0, 1000, "statusline", "m")

    def test_just_below_soft(self) -> None:
        assert classify_level(self._occ(99), self._prof()) is None

    def test_at_soft_inclusive(self) -> None:
        assert classify_level(self._occ(100), self._prof()) == "soft"

    def test_just_above_soft(self) -> None:
        assert classify_level(self._occ(101), self._prof()) == "soft"

    def test_just_below_hard(self) -> None:
        assert classify_level(self._occ(199), self._prof()) == "soft"

    def test_at_hard_inclusive(self) -> None:
        assert classify_level(self._occ(200), self._prof()) == "hard"


class TestEvaluateGuardStateMachine:
    def test_four_step_soft_debounce_and_rearm(self, tmp_path: Path) -> None:
        sid = "sess-sm"
        # 1. soft zone -> fires; nudge carries the occupancy AND threshold numbers (AC-4/B-QA-7).
        _write_sidecar(tmp_path, sid, 120)
        first = evaluate_guard({"session_id": sid}, state_dir=tmp_path, config=TINY_CONFIG)
        assert "120" in first["additionalContext"]  # used_tokens
        assert "100" in first["additionalContext"]  # soft threshold
        # 2. still soft -> silent.
        _write_sidecar(tmp_path, sid, 130)
        assert evaluate_guard({"session_id": sid}, state_dir=tmp_path, config=TINY_CONFIG) == {}
        # 3. drops below soft -> silent, flags cleared (re-arm).
        _write_sidecar(tmp_path, sid, 50)
        assert evaluate_guard({"session_id": sid}, state_dir=tmp_path, config=TINY_CONFIG) == {}
        # 4. back into soft -> fires again.
        _write_sidecar(tmp_path, sid, 140)
        again = evaluate_guard({"session_id": sid}, state_dir=tmp_path, config=TINY_CONFIG)
        assert "additionalContext" in again

    def test_hard_fires_once_and_sets_both_flags(self, tmp_path: Path) -> None:
        sid = "sess-hard"
        _write_sidecar(tmp_path, sid, 250)
        out = evaluate_guard({"session_id": sid}, state_dir=tmp_path, config=TINY_CONFIG)
        assert "HARD" in out["additionalContext"]
        assert "250" in out["additionalContext"]  # used_tokens
        assert "200" in out["additionalContext"]  # hard threshold
        assert evaluate_guard({"session_id": sid}, state_dir=tmp_path, config=TINY_CONFIG) == {}
        assert (tmp_path / f"context-guard-armed.{sid}").exists()
        assert (tmp_path / f"context-guard-hard.{sid}").exists()

    def test_soft_then_hard_escalates(self, tmp_path: Path) -> None:
        sid = "sess-esc"
        _write_sidecar(tmp_path, sid, 120)
        evaluate_guard({"session_id": sid}, state_dir=tmp_path, config=TINY_CONFIG)
        _write_sidecar(tmp_path, sid, 250)
        out = evaluate_guard({"session_id": sid}, state_dir=tmp_path, config=TINY_CONFIG)
        assert "HARD" in out["additionalContext"]

    def test_hard_then_soft_zone_silent(self, tmp_path: Path) -> None:
        sid = "sess-desc"
        _write_sidecar(tmp_path, sid, 250)
        evaluate_guard({"session_id": sid}, state_dir=tmp_path, config=TINY_CONFIG)
        _write_sidecar(tmp_path, sid, 150)  # soft zone, soft flag already set
        assert evaluate_guard({"session_id": sid}, state_dir=tmp_path, config=TINY_CONFIG) == {}

    def test_session_isolation(self, tmp_path: Path) -> None:
        _write_sidecar(tmp_path, "sess-a", 120)  # soft
        _write_sidecar(tmp_path, "sess-b", 10)  # below soft
        assert "additionalContext" in evaluate_guard(
            {"session_id": "sess-a"}, state_dir=tmp_path, config=TINY_CONFIG
        )
        assert (
            evaluate_guard({"session_id": "sess-b"}, state_dir=tmp_path, config=TINY_CONFIG) == {}
        )

    def test_invalid_session_id_no_signal_silent(self, tmp_path: Path) -> None:
        # No session_id, no transcript_path, project_root with no transcripts -> silence.
        out = evaluate_guard({}, state_dir=tmp_path, config=TINY_CONFIG, project_root=tmp_path)
        assert out == {}
        assert not any(tmp_path.glob("context-guard-*"))


# ---------------------------------------------------------------------------
# AC-5: handoff retention (FIFO).
# ---------------------------------------------------------------------------


class TestEnforceRetention:
    def test_evicts_oldest_keeps_cap(self, tmp_path: Path) -> None:
        for i in range(6):
            (tmp_path / f"HANDOFF-2026052{i}-120000.md").write_text("x", encoding="utf-8")
        removed = enforce_retention(handoff_dir=tmp_path, cap=5)
        remaining = sorted(p.name for p in tmp_path.glob("HANDOFF-*.md"))
        assert len(remaining) == 5
        assert len(removed) == 1
        assert removed[0].name == "HANDOFF-20260520-120000.md"  # oldest by name

    def test_under_cap_removes_nothing(self, tmp_path: Path) -> None:
        for i in range(3):
            (tmp_path / f"HANDOFF-2026052{i}-120000.md").write_text("x", encoding="utf-8")
        assert enforce_retention(handoff_dir=tmp_path, cap=5) == []

    def test_missing_dir_returns_empty(self, tmp_path: Path) -> None:
        assert enforce_retention(handoff_dir=tmp_path / "nope", cap=5) == []


# ---------------------------------------------------------------------------
# AC-6: auto-launch command builder (no process spawned).
# ---------------------------------------------------------------------------


class TestBuildLaunchCommand:
    def _handoff(self, tmp_path: Path) -> Path:
        path = tmp_path / "HANDOFF-20260523-120000.md"
        path.write_text("handoff", encoding="utf-8")
        return path

    def test_none_when_auth_off(self, tmp_path: Path) -> None:
        assert (
            build_launch_command(
                self._handoff(tmp_path),
                auth=False,
                allow_launch=True,
                depth=0,
                handoff_dir=tmp_path,
            )
            is None
        )

    def test_none_when_allow_launch_off(self, tmp_path: Path) -> None:
        assert (
            build_launch_command(
                self._handoff(tmp_path),
                auth=True,
                allow_launch=False,
                depth=0,
                handoff_dir=tmp_path,
            )
            is None
        )

    def test_none_when_depth_cap_reached(self, tmp_path: Path) -> None:
        assert (
            build_launch_command(
                self._handoff(tmp_path),
                auth=True,
                allow_launch=True,
                depth=1,
                max_depth=1,
                handoff_dir=tmp_path,
            )
            is None
        )

    def test_none_when_path_escapes_handoff_dir(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "escape.md"
        assert (
            build_launch_command(
                outside, auth=True, allow_launch=True, depth=0, max_depth=1, handoff_dir=tmp_path
            )
            is None
        )

    def test_valid_returns_single_positional_prompt_with_validated_path(
        self, tmp_path: Path
    ) -> None:
        handoff = self._handoff(tmp_path)
        cmd = build_launch_command(
            handoff, auth=True, allow_launch=True, depth=0, max_depth=1, handoff_dir=tmp_path
        )
        assert cmd is not None
        assert cmd[:2] == ["claude", "--print"]
        # Single-positional prompt (what `claude --print` accepts); the validated,
        # containment-checked path is inlined — injection-safe under shell=False.
        assert len(cmd) == 3
        assert str(handoff.resolve()) in cmd[2]


# ---------------------------------------------------------------------------
# build_sidecar_record shape.
# ---------------------------------------------------------------------------


def test_build_sidecar_record_has_required_fields() -> None:
    occ = Occupancy(140000, 14.0, 1_000_000, "statusline", "claude-opus-4-7")
    prof = resolve_threshold("claude-opus-4-7")
    rec = build_sidecar_record(occ, prof, "sess-1", now=123.0)
    assert rec["session_id"] == "sess-1"
    assert rec["tier"] == "opus_1m"
    assert rec["written_at_epoch"] == 123.0
    assert rec["source"] == "statusline"
