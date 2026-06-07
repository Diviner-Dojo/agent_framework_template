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
