"""Tests for scripts/session_supervisor.py — autonomous multi-session supervisor.

Pure seams (build_prompt, build_command, parse_result, result_tokens,
classify_result) are tested directly. The supervise() loop is tested with an
injected runner so no real `claude -p` subprocess is spawned.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import session_supervisor as sup


class _Proc:
    """Minimal subprocess.CompletedProcess stand-in."""

    def __init__(self, rc: int = 0, out: str = "{}", err: str = "") -> None:
        self.returncode = rc
        self.stdout = out
        self.stderr = err


class TestDefaultRunner:
    @pytest.mark.regression
    def test_resolves_executable_via_which(self, monkeypatch) -> None:
        # Regression (2026-06-07): on Windows `claude` is `claude.CMD`; a bare
        # subprocess.run(["claude", ...], shell=False) raises FileNotFoundError
        # (CreateProcess ignores PATHEXT). The runner must resolve cmd[0].
        captured: dict = {}
        monkeypatch.setattr(sup.shutil, "which", lambda _n: "/abs/claude.CMD")
        monkeypatch.setattr(
            sup.subprocess,
            "run",
            lambda argv, **kw: captured.__setitem__("argv", argv) or _Proc(),
        )
        rc, out, err = sup._default_runner(["claude", "-p", "hi"], Path("."), 10)
        assert rc == 0
        assert captured["argv"][0] == "/abs/claude.CMD"
        assert captured["argv"][1:] == ["-p", "hi"]

    def test_falls_back_to_bare_name_when_which_none(self, monkeypatch) -> None:
        captured: dict = {}
        monkeypatch.setattr(sup.shutil, "which", lambda _n: None)
        monkeypatch.setattr(
            sup.subprocess,
            "run",
            lambda argv, **kw: captured.__setitem__("argv", argv) or _Proc(),
        )
        sup._default_runner(["claude", "-p", "x"], Path("."), 10)
        assert captured["argv"][0] == "claude"

    def test_timeout_returns_124(self, monkeypatch) -> None:
        monkeypatch.setattr(sup.shutil, "which", lambda _n: "claude")

        def _raise(argv, **kw):
            raise sup.subprocess.TimeoutExpired(cmd=argv, timeout=1)

        monkeypatch.setattr(sup.subprocess, "run", _raise)
        rc, out, err = sup._default_runner(["claude", "-p", "x"], Path("."), 1)
        assert rc == 124 and "timed out" in err


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _result_json(
    *,
    text: str = "",
    is_error: bool = False,
    cost: float = 0.0,
    in_tok: int = 0,
    out_tok: int = 0,
) -> str:
    """Render a `--output-format json` result object as one line."""
    return json.dumps(
        {
            "type": "result",
            "subtype": "error" if is_error else "success",
            "is_error": is_error,
            "result": text,
            "total_cost_usd": cost,
            "usage": {"input_tokens": in_tok, "output_tokens": out_tok},
            "session_id": "test-sid",
        }
    )


class _ScriptedRunner:
    """Runner returning a queued (rc, stdout, stderr) per call; records calls."""

    def __init__(self, results: list[tuple[int, str, str]]) -> None:
        self._results = list(results)
        self.calls: list[tuple] = []

    def __call__(self, cmd, cwd, timeout):
        self.calls.append((cmd, cwd, timeout))
        return self._results.pop(0)


def _always(result: tuple[int, str, str]):
    """A runner that returns the same result on every call."""
    runner = _ScriptedRunner([])
    runner._results = []  # never used

    def _run(cmd, cwd, timeout):
        runner.calls.append((cmd, cwd, timeout))
        return result

    _run.calls = runner.calls  # type: ignore[attr-defined]
    return _run


# --------------------------------------------------------------------------- #
# build_prompt / build_command (pure)
# --------------------------------------------------------------------------- #
class TestBuildPromptAndCommand:
    def test_prompt_carries_handoff_path_and_both_sentinels(self, tmp_path) -> None:
        hp = tmp_path / "HANDOFF.md"
        prompt = sup.build_prompt(hp)
        assert str(hp) in prompt
        assert sup.SENTINEL_DONE in prompt
        assert sup.SENTINEL_ROLL in prompt

    def test_prompt_rejects_control_chars_in_path(self) -> None:
        # A path with a newline + sentinel could spoof DONE/ROLL — must be rejected.
        from pathlib import PurePosixPath

        bad = PurePosixPath("/tmp/h.md\nSUPERVISOR_DONE")
        with pytest.raises(ValueError):
            sup.build_prompt(bad)  # type: ignore[arg-type]

    def test_command_has_bypass_permissions_and_no_bare(self) -> None:
        cmd = sup.build_command("p")
        assert cmd[:2] == ["claude", "-p"]
        assert "--permission-mode" in cmd
        assert cmd[cmd.index("--permission-mode") + 1] == "bypassPermissions"
        assert "--output-format" in cmd
        # --bare would break OAuth auth AND skip the safety hooks — must be absent.
        assert "--bare" not in cmd

    def test_command_includes_optional_caps(self) -> None:
        cmd = sup.build_command("p", max_turns=12, max_budget_usd=3.5)
        assert cmd[cmd.index("--max-turns") + 1] == "12"
        assert cmd[cmd.index("--max-budget-usd") + 1] == "3.5"

    def test_command_omits_caps_when_none(self) -> None:
        cmd = sup.build_command("p", max_turns=None, max_budget_usd=None)
        assert "--max-turns" not in cmd
        assert "--max-budget-usd" not in cmd


# --------------------------------------------------------------------------- #
# parse_result / result_tokens (pure)
# --------------------------------------------------------------------------- #
class TestParseResult:
    def test_parses_single_json_line(self) -> None:
        parsed = sup.parse_result(_result_json(text="hi", cost=1.0))
        assert parsed is not None
        assert parsed["result"] == "hi"

    def test_ignores_leading_log_lines(self) -> None:
        out = "INFO booting\nsome noise\n" + _result_json(text="done")
        parsed = sup.parse_result(out)
        assert parsed is not None and parsed["result"] == "done"

    def test_malformed_returns_none(self) -> None:
        assert sup.parse_result("{not json\nalso not") is None

    def test_empty_returns_none(self) -> None:
        assert sup.parse_result("") is None

    def test_non_result_json_ignored(self) -> None:
        # A dict without result/subtype is not a result object.
        assert sup.parse_result(json.dumps({"foo": "bar"})) is None

    def test_result_tokens_sums_input_and_output(self) -> None:
        parsed = sup.parse_result(_result_json(in_tok=100, out_tok=23))
        assert sup.result_tokens(parsed) == 123

    def test_result_tokens_absent_is_zero(self) -> None:
        assert sup.result_tokens({"result": "x"}) == 0


# --------------------------------------------------------------------------- #
# classify_result (pure)
# --------------------------------------------------------------------------- #
class TestClassifyResult:
    def test_none_is_error(self) -> None:
        assert sup.classify_result(None) == "error"

    def test_is_error_flag(self) -> None:
        assert sup.classify_result({"is_error": True, "result": "SUPERVISOR_DONE"}) == "error"

    def test_done_sentinel(self) -> None:
        assert sup.classify_result({"result": "all good SUPERVISOR_DONE"}) == "done"

    def test_roll_sentinel(self) -> None:
        assert sup.classify_result({"result": "more to do SUPERVISOR_ROLL"}) == "roll"

    def test_done_wins_over_roll(self) -> None:
        # A completed task must never be relaunched.
        assert sup.classify_result({"result": "SUPERVISOR_ROLL ... SUPERVISOR_DONE"}) == "done"

    def test_no_sentinel_is_unknown(self) -> None:
        assert sup.classify_result({"result": "finished my turn"}) == "unknown"


# --------------------------------------------------------------------------- #
# supervise (loop, injected runner)
# --------------------------------------------------------------------------- #
class TestSupervise:
    def test_handoff_missing(self, tmp_path) -> None:
        out = sup.supervise(
            tmp_path / "nope.md",
            runner=_always((0, "", "")),
            progress_log=tmp_path / "p.md",
            cwd=tmp_path,
        )
        assert out["outcome"] == "handoff-missing"
        assert out["sessions"] == 0

    def test_dirty_tree_aborts(self, tmp_path) -> None:
        hp = tmp_path / "h.md"
        hp.write_text("x", encoding="utf-8")

        def _boom(cmd, cwd, timeout):
            raise AssertionError("must not spawn on a dirty tree")

        out = sup.supervise(
            hp,
            runner=_boom,
            tree_checker=lambda _c: False,
            progress_log=tmp_path / "p.md",
            cwd=tmp_path,
        )
        assert out["outcome"] == "dirty-tree" and out["sessions"] == 0

    def test_allow_dirty_overrides_preflight(self, tmp_path) -> None:
        hp = tmp_path / "h.md"
        hp.write_text("x", encoding="utf-8")
        runner = _ScriptedRunner([(0, _result_json(text="SUPERVISOR_DONE", cost=0.1), "")])
        out = sup.supervise(
            hp,
            runner=runner,
            tree_checker=lambda _c: False,
            allow_dirty=True,
            progress_log=tmp_path / "p.md",
            cwd=tmp_path,
        )
        assert out["outcome"] == "done"

    def test_done_first_session(self, tmp_path) -> None:
        hp = tmp_path / "h.md"
        hp.write_text("x", encoding="utf-8")
        runner = _ScriptedRunner([(0, _result_json(text="SUPERVISOR_DONE", cost=1.5), "")])
        out = sup.supervise(hp, runner=runner, progress_log=tmp_path / "p.md", cwd=tmp_path)
        assert out == {"sessions": 1, "outcome": "done", "cost_usd": 1.5}
        assert len(runner.calls) == 1

    def test_roll_then_done(self, tmp_path) -> None:
        hp = tmp_path / "h.md"
        hp.write_text("x", encoding="utf-8")
        runner = _ScriptedRunner(
            [
                (0, _result_json(text="SUPERVISOR_ROLL", cost=1.0), ""),
                (0, _result_json(text="SUPERVISOR_DONE", cost=2.0), ""),
            ]
        )
        out = sup.supervise(hp, runner=runner, progress_log=tmp_path / "p.md", cwd=tmp_path)
        assert out["outcome"] == "done" and out["sessions"] == 2
        assert out["cost_usd"] == pytest.approx(3.0)

    def test_roll_hits_max_sessions(self, tmp_path) -> None:
        hp = tmp_path / "h.md"
        hp.write_text("x", encoding="utf-8")
        runner = _always((0, _result_json(text="SUPERVISOR_ROLL", cost=0.5), ""))
        out = sup.supervise(
            hp, runner=runner, max_sessions=3, progress_log=tmp_path / "p.md", cwd=tmp_path
        )
        assert out["outcome"] == "max-sessions" and out["sessions"] == 3
        assert out["cost_usd"] == pytest.approx(1.5)

    def test_unknown_sentinel_stops(self, tmp_path) -> None:
        hp = tmp_path / "h.md"
        hp.write_text("x", encoding="utf-8")
        runner = _always((0, _result_json(text="just finished"), ""))
        out = sup.supervise(hp, runner=runner, progress_log=tmp_path / "p.md", cwd=tmp_path)
        assert out["outcome"] == "unknown-stop" and out["sessions"] == 1

    def test_error_returncode_stops(self, tmp_path) -> None:
        hp = tmp_path / "h.md"
        hp.write_text("x", encoding="utf-8")
        runner = _always((1, "", "boom"))
        out = sup.supervise(hp, runner=runner, progress_log=tmp_path / "p.md", cwd=tmp_path)
        assert out["outcome"] == "error" and out["sessions"] == 1

    def test_is_error_result_stops(self, tmp_path) -> None:
        hp = tmp_path / "h.md"
        hp.write_text("x", encoding="utf-8")
        runner = _always((0, _result_json(text="SUPERVISOR_ROLL", is_error=True), ""))
        out = sup.supervise(hp, runner=runner, progress_log=tmp_path / "p.md", cwd=tmp_path)
        assert out["outcome"] == "error"

    def test_budget_cap_stops(self, tmp_path) -> None:
        hp = tmp_path / "h.md"
        hp.write_text("x", encoding="utf-8")
        runner = _always((0, _result_json(text="SUPERVISOR_ROLL", cost=3.0), ""))
        out = sup.supervise(
            hp,
            runner=runner,
            max_budget_usd=5.0,
            max_sessions=10,
            progress_log=tmp_path / "p.md",
            cwd=tmp_path,
        )
        assert out["outcome"] == "budget" and out["sessions"] == 2
        assert out["cost_usd"] == pytest.approx(6.0)

    def test_dry_run_does_not_spawn(self, tmp_path) -> None:
        hp = tmp_path / "h.md"
        hp.write_text("x", encoding="utf-8")

        def _boom(cmd, cwd, timeout):
            raise AssertionError("runner must not be called in dry-run")

        out = sup.supervise(
            hp, runner=_boom, dry_run=True, progress_log=tmp_path / "p.md", cwd=tmp_path
        )
        assert out["outcome"] == "dry-run"

    def test_progress_log_is_written(self, tmp_path) -> None:
        hp = tmp_path / "h.md"
        hp.write_text("x", encoding="utf-8")
        log = tmp_path / "prog.md"
        runner = _ScriptedRunner([(0, _result_json(text="SUPERVISOR_DONE", cost=0.2), "")])
        sup.supervise(hp, runner=runner, progress_log=log, cwd=tmp_path)
        # The progress log is the evidence trail the developer asked for.
        text = log.read_text(encoding="utf-8")
        assert "session 1" in text and "DONE" in text


# --------------------------------------------------------------------------- #
# Turn-budget prompt (work item 2b)
# --------------------------------------------------------------------------- #
class TestTurnBudgetPrompt:
    @pytest.mark.regression
    def test_prompt_names_cap_and_checkpoint_turn(self, tmp_path) -> None:
        # Regression (2026-06-12 07:09): an 80-turn clip killed a session with
        # no chance to emit a sentinel -> no-sentinel chain stop. The prompt
        # must name the cap and a checkpoint turn ~10 before it.
        prompt = sup.build_prompt(tmp_path / "h.md", max_turns=80)
        assert "80" in prompt and "70" in prompt
        assert sup.SENTINEL_ROLL in prompt

    def test_prompt_without_cap_omits_budget_clause(self, tmp_path) -> None:
        prompt = sup.build_prompt(tmp_path / "h.md")
        assert "TURN BUDGET" not in prompt

    def test_checkpoint_turn_floors_at_one(self, tmp_path) -> None:
        prompt = sup.build_prompt(tmp_path / "h.md", max_turns=5)
        assert "by turn 1" in prompt


# --------------------------------------------------------------------------- #
# MODEL: tiering (work item 2c)
# --------------------------------------------------------------------------- #
class TestModelTiering:
    def test_parse_handoff_model_finds_header_line(self) -> None:
        text = "# NEXT RUN: Run 3 (manifests)\nMODEL: sonnet\n\nDo the things."
        assert sup.parse_handoff_model(text) == "sonnet"

    def test_parse_handoff_model_absent_is_none(self) -> None:
        assert sup.parse_handoff_model("# NEXT RUN\nno tier here") is None

    def test_parse_handoff_model_ignores_inline_mentions(self) -> None:
        # Only a line-start "MODEL:" declares the tier; prose mentions don't.
        assert sup.parse_handoff_model("the MODEL: sonnet idea is nice") is None

    def test_parse_handoff_model_rejects_argv_smuggling(self) -> None:
        # A value with spaces/flags must not match (charset-restricted group).
        assert sup.parse_handoff_model("MODEL: sonnet --dangerously-skip") is None

    def test_parse_handoff_model_rejects_leading_hyphen_or_dot(self) -> None:
        # sec F2 fold (DISC-20260612-190124): "MODEL: -h" would reach argv as
        # "--model -h"; first char must be alphanumeric.
        assert sup.parse_handoff_model("MODEL: -h") is None
        assert sup.parse_handoff_model("MODEL: ..evil") is None

    def test_build_command_carries_model(self) -> None:
        cmd = sup.build_command("p", model="fable")
        assert cmd[cmd.index("--model") + 1] == "fable"

    def test_build_command_omits_model_when_none(self) -> None:
        assert "--model" not in sup.build_command("p", model=None)

    def test_supervise_passes_handoff_model_to_command(self, tmp_path) -> None:
        hp = tmp_path / "h.md"
        hp.write_text("# NEXT RUN\nMODEL: sonnet\nwork", encoding="utf-8")
        runner = _ScriptedRunner([(0, _result_json(text="SUPERVISOR_DONE"), "")])
        sup.supervise(hp, runner=runner, progress_log=tmp_path / "p.md", cwd=tmp_path)
        cmd = runner.calls[0][0]
        assert cmd[cmd.index("--model") + 1] == "sonnet"

    def test_supervise_rereads_model_each_session(self, tmp_path) -> None:
        # The rolling handoff is updated in place between runs; a tier change
        # in the NEXT RUN header must take effect on the next spawn.
        hp = tmp_path / "h.md"
        hp.write_text("MODEL: sonnet\nwork", encoding="utf-8")
        calls: list[list[str]] = []

        def _runner(cmd, cwd, timeout):
            calls.append(cmd)
            hp.write_text("MODEL: fable\nmore work", encoding="utf-8")
            text = "SUPERVISOR_DONE" if len(calls) > 1 else "SUPERVISOR_ROLL"
            return (0, _result_json(text=text), "")

        sup.supervise(hp, runner=_runner, progress_log=tmp_path / "p.md", cwd=tmp_path)
        assert calls[0][calls[0].index("--model") + 1] == "sonnet"
        assert calls[1][calls[1].index("--model") + 1] == "fable"


# --------------------------------------------------------------------------- #
# Usage-limit detection + sleep-until-reset (work item 2a)
# --------------------------------------------------------------------------- #
# The real kill line as recorded in .supervisor-progress.md (2026-06-11 17:47,
# 2026-06-12 07:46) — interpunct arrives mojibake'd through the cp1252 console.
_LIMIT_TEXT = "You've hit your session limit Â· resets 10pm (America/Los_Angeles)"


def _local_epoch(hour: int, minute: int = 0) -> float:
    """Epoch seconds for today at hour:minute local time."""
    import time as _time

    lt = _time.localtime()
    return _time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, hour, minute, 0, 0, 0, -1))


class TestUsageLimitDetection:
    def test_detects_in_result_text(self) -> None:
        parsed = {"result": _LIMIT_TEXT, "is_error": True}
        assert sup.detect_usage_limit(parsed, "", "") == _LIMIT_TEXT

    def test_detects_in_stderr(self) -> None:
        assert sup.detect_usage_limit(None, "", _LIMIT_TEXT) == _LIMIT_TEXT

    def test_plain_error_is_none(self) -> None:
        assert sup.detect_usage_limit({"result": "boom"}, "", "traceback") is None

    def test_reset_seconds_future_same_day(self) -> None:
        # now=17:47, resets 10pm -> 4h13m + 5min slack
        secs = sup.parse_reset_seconds(_LIMIT_TEXT, now=_local_epoch(17, 47))
        assert secs == (4 * 3600 + 13 * 60) + 300

    def test_reset_seconds_past_rolls_to_tomorrow(self) -> None:
        # now=23:00, resets 10pm -> tomorrow 22:00
        secs = sup.parse_reset_seconds(_LIMIT_TEXT, now=_local_epoch(23, 0))
        assert secs == 23 * 3600 + 300

    def test_reset_seconds_parses_minutes_and_noon_midnight(self) -> None:
        secs = sup.parse_reset_seconds("resets 3:30pm", now=_local_epoch(15, 0))
        assert secs == 30 * 60 + 300
        secs = sup.parse_reset_seconds("resets 12am", now=_local_epoch(23, 0))
        assert secs == 3600 + 300
        secs = sup.parse_reset_seconds("resets 12pm", now=_local_epoch(11, 0))
        assert secs == 3600 + 300

    def test_unparseable_reset_is_none(self) -> None:
        assert sup.parse_reset_seconds("hit your session limit, try later") is None

    def test_detects_in_stdout(self) -> None:
        # qa F2 fold (DISC-20260612-190124): the third candidate slot.
        assert sup.detect_usage_limit(None, _LIMIT_TEXT, "") == _LIMIT_TEXT

    def test_reset_seconds_at_exact_reset_time_rolls_to_tomorrow(self) -> None:
        # qa F1 fold (DISC-20260612-190124): pins the <= operator — a reset
        # advertised for exactly `now` was just consumed; wait a full day.
        secs = sup.parse_reset_seconds(_LIMIT_TEXT, now=_local_epoch(22, 0))
        assert secs == 24 * 3600 + 300


class TestSuperviseUsageLimitRetry:
    @pytest.mark.regression
    def test_limit_kill_sleeps_and_retries(self, tmp_path) -> None:
        # Regression (2026-06-11 17:47 + 2026-06-12 07:46): the supervisor
        # treated a usage-limit kill as a hard error and stopped the chain,
        # wasting the post-reset night. It must sleep until reset and retry.
        hp = tmp_path / "h.md"
        hp.write_text("x", encoding="utf-8")
        runner = _ScriptedRunner(
            [
                (1, _result_json(text=_LIMIT_TEXT, is_error=True, cost=4.6), ""),
                (0, _result_json(text="SUPERVISOR_DONE", cost=1.0), ""),
            ]
        )
        naps: list[float] = []
        out = sup.supervise(
            hp,
            runner=runner,
            progress_log=tmp_path / "p.md",
            cwd=tmp_path,
            sleeper=naps.append,
        )
        assert out["outcome"] == "done" and out["sessions"] == 2
        assert out["cost_usd"] == pytest.approx(5.6)
        assert len(naps) == 1 and naps[0] > 0

    def test_unparseable_reset_uses_fallback_sleep(self, tmp_path) -> None:
        hp = tmp_path / "h.md"
        hp.write_text("x", encoding="utf-8")
        runner = _ScriptedRunner(
            [
                (1, "", "You've hit your session limit, no time given"),
                (0, _result_json(text="SUPERVISOR_DONE"), ""),
            ]
        )
        naps: list[float] = []
        out = sup.supervise(
            hp, runner=runner, progress_log=tmp_path / "p.md", cwd=tmp_path, sleeper=naps.append
        )
        assert out["outcome"] == "done"
        assert naps == [sup.DEFAULT_LIMIT_FALLBACK_SLEEP]

    def test_retries_capped_then_usage_limit_outcome(self, tmp_path) -> None:
        hp = tmp_path / "h.md"
        hp.write_text("x", encoding="utf-8")
        runner = _always((1, _result_json(text=_LIMIT_TEXT, is_error=True), ""))
        naps: list[float] = []
        out = sup.supervise(
            hp,
            runner=runner,
            max_limit_retries=2,
            max_sessions=10,
            progress_log=tmp_path / "p.md",
            cwd=tmp_path,
            sleeper=naps.append,
        )
        assert out["outcome"] == "usage-limit"
        assert out["sessions"] == 3  # initial + 2 retries
        assert len(naps) == 2

    def test_non_limit_error_still_stops_without_sleep(self, tmp_path) -> None:
        hp = tmp_path / "h.md"
        hp.write_text("x", encoding="utf-8")
        runner = _always((1, "", "boom"))

        def _no_sleep(_s: float) -> None:
            raise AssertionError("must not sleep on a non-limit error")

        out = sup.supervise(
            hp, runner=runner, progress_log=tmp_path / "p.md", cwd=tmp_path, sleeper=_no_sleep
        )
        assert out["outcome"] == "error" and out["sessions"] == 1

    def test_limit_kill_at_session_cap_skips_sleep_and_labels_cause(self, tmp_path) -> None:
        # sec F1 + qa F3 fold (DISC-20260612-190124): a limit kill with no
        # session slot left must not sleep, and the outcome must name the
        # usage limit, not masquerade as a normal max-sessions expiry.
        hp = tmp_path / "h.md"
        hp.write_text("x", encoding="utf-8")
        runner = _always((1, _result_json(text=_LIMIT_TEXT, is_error=True), ""))

        def _no_sleep(_s: float) -> None:
            raise AssertionError("must not sleep when no session slot remains")

        out = sup.supervise(
            hp,
            runner=runner,
            max_sessions=1,
            progress_log=tmp_path / "p.md",
            cwd=tmp_path,
            sleeper=_no_sleep,
        )
        assert out["outcome"] == "usage-limit" and out["sessions"] == 1

    def test_budget_exhausted_blocks_limit_retry(self, tmp_path) -> None:
        # A retry spawns another costly session; an exhausted budget must win.
        hp = tmp_path / "h.md"
        hp.write_text("x", encoding="utf-8")
        runner = _always((1, _result_json(text=_LIMIT_TEXT, is_error=True, cost=6.0), ""))

        def _no_sleep(_s: float) -> None:
            raise AssertionError("must not sleep when the budget is exhausted")

        out = sup.supervise(
            hp,
            runner=runner,
            max_budget_usd=5.0,
            progress_log=tmp_path / "p.md",
            cwd=tmp_path,
            sleeper=_no_sleep,
        )
        assert out["outcome"] == "budget" and out["sessions"] == 1
