"""Tests for .claude/hooks/validate_tool_use.py — protected paths and the Bash command guard.

Closes review finding M4 ("PROTECTED_PATTERNS is untested in both trees") and covers the new
Bash command guard added to close the ``Bash(*)`` bypass: until now the validator was wired only
on the ``Write|Edit`` PreToolUse matcher, so a shell command could write, truncate or delete any
protected path without the hook emitting any decision at all.

Both directions are tested deliberately:
  * ``TestBashGuardRefuses``      — destructive shapes are denied / asked.
  * ``TestBashGuardAllows``       — ordinary commands, including read-only ones that merely
                                    *mention* a protected path, are untouched.
  * ``TestEndToEndHookProtocol``  — the real stdin→stdout hook contract, not just the helper.

The false-negative direction matters as much as the false-positive one: a guard that blocks
ordinary work gets switched off, which is the same outcome as no guard at all.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK_PATH = REPO_ROOT / ".claude" / "hooks" / "validate_tool_use.py"


def _load_hook_module() -> ModuleType:
    """Import the hook by path — .claude/hooks is not an importable package."""
    spec = importlib.util.spec_from_file_location("validate_tool_use_under_test", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hook = _load_hook_module()


def _run_hook(payload: dict) -> dict | None:
    """Run the hook as a subprocess exactly as Claude Code does. None means 'no decision'."""
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=30,
    )
    assert proc.returncode == 0, f"hook must always exit 0, got {proc.returncode}: {proc.stderr}"
    out = proc.stdout.strip()
    return json.loads(out) if out else None


def _decision(command: str) -> str | None:
    verdict = hook.check_bash_command(command)
    return None if verdict is None else verdict[0]


# ---------------------------------------------------------------------------
# The incident this guard exists for
# ---------------------------------------------------------------------------

INCIDENT_TRUNCATE = ": > discussions/2026-08-07/DISC-20260807-063650-x/events.jsonl"
INCIDENT_SQL = "sqlite3 metrics/evaluation.db \"DELETE FROM findings WHERE discussion_id='x'\""
# The same two acts, expressed in this repo's DECLARED PRIMARY SHELL. `: > file` has no PowerShell
# spelling; `Clear-Content` and `Set-Content -Value ''` are how you empty a file there, and the
# agent has a `PowerShell` tool distinct from `Bash` with which to run them.
INCIDENT_TRUNCATE_PWSH = "Clear-Content discussions/2026-08-07/DISC-20260807-063650-x/events.jsonl"
INCIDENT_TRUNCATE_PWSH_SET = (
    "Set-Content -Path discussions/2026-08-07/DISC-20260807-063650-x/events.jsonl -Value ''"
)
INCIDENT_DELETE_PWSH = r"Remove-Item -Recurse -Force discussions\2026-08-07"


@pytest.mark.regression
class TestIncidentRegression:
    """A subagent truncated a sealed events.jsonl and ran DELETEs against evaluation.db.

    Both paths were already in PROTECTED_PATTERNS. Nothing stopped either, because the validator
    was wired only on Write|Edit. These two commands are the literal shapes that got through.
    """

    def test_colon_truncation_of_sealed_events_log_is_denied(self) -> None:
        assert _decision(INCIDENT_TRUNCATE) == "deny"

    def test_sqlite_delete_against_evaluation_db_is_denied(self) -> None:
        assert _decision(INCIDENT_SQL) == "deny"

    @pytest.mark.parametrize(
        "command",
        [INCIDENT_TRUNCATE_PWSH, INCIDENT_TRUNCATE_PWSH_SET, INCIDENT_DELETE_PWSH],
    )
    def test_powershell_twin_of_the_incident_is_denied(self, command: str) -> None:
        """The incident's POSIX spelling was guarded while its PowerShell spelling was not.

        A review of the first draft ran 20 PowerShell/cmd destructive shapes through
        ``check_bash_command`` and got ALLOW on all 20 — on a repo whose environment block
        declares PowerShell the primary shell. A guard that only knows the shell the agent is
        *not* using is decoration.
        """
        assert _decision(command) == "deny"

    def test_incident_commands_deny_through_the_real_hook_protocol(self) -> None:
        for command in (INCIDENT_TRUNCATE, INCIDENT_SQL):
            result = _run_hook({"tool_name": "Bash", "tool_input": {"command": command}})
            assert result is not None, f"hook emitted no decision for {command!r}"
            assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_powershell_tool_payloads_are_routed_to_the_guard(self) -> None:
        """The `PowerShell` tool is a separate tool name — routing must name it, not infer it."""
        for command in (INCIDENT_TRUNCATE_PWSH, INCIDENT_DELETE_PWSH):
            result = _run_hook({"tool_name": "PowerShell", "tool_input": {"command": command}})
            assert result is not None, f"hook emitted no decision for {command!r}"
            assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_guard_can_fail_when_the_protected_path_is_removed(self) -> None:
        """Prove the assertions above are load-bearing, not vacuously true.

        If ``discussions`` were dropped from the deny set, the incident command would sail
        through — which is precisely the pre-fix behaviour.
        """
        original = hook.BASH_DENY_DIRS
        try:
            hook.BASH_DENY_DIRS = tuple(d for d in original if d != "discussions")
            assert _decision(INCIDENT_TRUNCATE) is None
            assert _decision(INCIDENT_TRUNCATE_PWSH) is None
        finally:
            hook.BASH_DENY_DIRS = original
        assert _decision(INCIDENT_TRUNCATE) == "deny"
        assert _decision(INCIDENT_TRUNCATE_PWSH) == "deny"

    def test_guard_can_fail_when_the_powershell_verbs_are_removed(self) -> None:
        """Prove the PowerShell coverage is carried by the verb tables, not by something else.

        Strip the cmdlets back to the POSIX-only set the first draft shipped and the PowerShell
        twins must return to ALLOW — reproducing, in-suite, the exact hole the review measured.
        """
        posix_only_all = {"rm", "unlink", "shred", "truncate", "chmod", "chown", "mv", "tee", "dd"}
        original_all, original_destroy = hook.DESTRUCTIVE_ALL_ARGS, hook.DESTROY_VERBS
        try:
            hook.DESTRUCTIVE_ALL_ARGS = posix_only_all
            hook.DESTROY_VERBS = posix_only_all
            for command in (
                INCIDENT_TRUNCATE_PWSH,
                INCIDENT_TRUNCATE_PWSH_SET,
                INCIDENT_DELETE_PWSH,
            ):
                assert _decision(command) is None, f"expected the pre-fix hole for {command!r}"
        finally:
            hook.DESTRUCTIVE_ALL_ARGS = original_all
            hook.DESTROY_VERBS = original_destroy
        assert _decision(INCIDENT_DELETE_PWSH) == "deny"


# ---------------------------------------------------------------------------
# Direction 1: destructive commands are refused
# ---------------------------------------------------------------------------


class TestBashGuardRefuses:
    @pytest.mark.parametrize(
        "command",
        [
            # redirection — truncate
            "echo hi > discussions/2026-01-01/D/events.jsonl",
            ": > metrics/evaluation.db",
            "true > .claude/settings.json",
            "cat foo > .git/config",
            # redirection — append into a non-append-only protected path
            "echo x >> metrics/evaluation.db",
            "echo x >> .claude/settings.json",
            # tee
            "echo '{}' | tee metrics/evaluation.db",
            "cat payload | tee .claude/hooks/validate_tool_use.py",
            # rm / mv / shred / truncate
            "rm -rf discussions/2026-08-07",
            "rm discussions/2026-08-07/D/events.jsonl",
            "mv discussions/2026-08-07 /tmp/gone",
            "shred -u metrics/evaluation.db",
            "truncate -s 0 metrics/evaluation.db",
            # cp destination
            "cp /tmp/fake.db metrics/evaluation.db",
            "cp /tmp/settings.json .claude/settings.json",
            # chmod / chown
            "chmod 777 discussions/2026-08-07/D/events.jsonl",
            "chmod -R 666 .git/objects",
            # sed -i
            "sed -i 's/a/b/' .claude/settings.json",
            "sed -i.bak 's/x/y/' discussions/2026-08-07/D/transcript.md",
            # git destructive subcommands with an explicit path
            "git rm -r discussions/2026-08-07",
            "git checkout -- discussions/2026-08-07",
            # dd
            "dd if=/dev/zero of=metrics/evaluation.db",
            # sqlite3 row/schema destruction
            'sqlite3 metrics/evaluation.db "DROP TABLE findings"',
            'sqlite3 metrics/evaluation.db "ALTER TABLE findings ADD COLUMN x TEXT"',
            'sqlite3 metrics/evaluation.db "DELETE FROM turns"',
            # inline python
            "python -c \"open('metrics/evaluation.db','w').close()\"",
            "python3 -c \"import pathlib; pathlib.Path('discussions/a/events.jsonl').unlink()\"",
            "python -c \"import shutil; shutil.rmtree('discussions/2026-08-07')\"",
            # inline python via HEREDOC — how an agent actually does bulk file surgery
            "python - <<'PY'\nimport pathlib\n"
            "pathlib.Path('discussions/a/events.jsonl').write_text('')\nPY",
            "python3 <<EOF\nimport sqlite3\n"
            "sqlite3.connect('metrics/evaluation.db').execute('DELETE FROM findings')\nEOF",
            # wrapped / nested command forms
            "bash -c 'rm -rf discussions/2026-08-07'",
            'sh -c ": > metrics/evaluation.db"',
            "sudo rm -rf discussions/2026-08-07",
            "find discussions -name '*.jsonl' | xargs rm",
            # chained / hidden behind another command
            "cd /tmp && rm -rf discussions/2026-08-07",
            "ls; rm metrics/evaluation.db",
            "find discussions -name '*.jsonl' -delete",
        ],
    )
    def test_destructive_command_is_refused(self, command: str) -> None:
        assert _decision(command) == "deny", f"guard allowed a destructive command: {command!r}"

    def test_env_overwrite_asks_rather_than_denies(self) -> None:
        """.env has a plausible legitimate developer overwrite, so it is recoverable-by-ask."""
        assert _decision("echo 'K=v' > .env") == "ask"
        assert _decision("rm .env") == "ask"

    @pytest.mark.parametrize(
        "command",
        [
            "sqlite3 metrics/evaluation.db \"UPDATE reflections SET promoted = 1 WHERE id = 'x'\"",
            'sqlite3 metrics/evaluation.db "INSERT INTO findings VALUES (1)"',
            "python -c \"import sqlite3; sqlite3.connect('metrics/evaluation.db')"
            ".execute('UPDATE reflections SET promoted = 1')\"",
        ],
    )
    def test_non_destructive_dml_asks_rather_than_denies(self, command: str) -> None:
        """MEASURED CORRECTION — /promote UPDATEs evaluation.db from an inline python block.

        An earlier draft of this guard denied all DML. Running it over this repo's own documented
        commands flagged `.claude/commands/promote.md` twice: denying UPDATE would have broken a
        shipped command on day one. `grep -rhoiE 'UPDATE [a-z_]+' .claude/commands/`
        returns 40 hits and zero DELETE/DROP/ALTER, so the destructive/non-destructive
        split is drawn where the evidence actually falls.
        """
        assert _decision(command) == "ask"

    def test_file_level_destruction_of_the_db_still_denies(self) -> None:
        """The UPDATE carve-out must not soften destruction of the database file itself."""
        assert _decision("rm metrics/evaluation.db") == "deny"
        assert _decision("python -c \"open('metrics/evaluation.db','w').close()\"") == "deny"

    def test_deny_outranks_ask_when_both_are_present(self) -> None:
        assert _decision("rm .env metrics/evaluation.db") == "deny"

    def test_reason_names_the_path_and_states_the_limit(self) -> None:
        verdict = hook.check_bash_command(INCIDENT_TRUNCATE)
        assert verdict is not None
        _, reason = verdict
        assert "discussions/" in reason
        # The message must not oversell the guard — a prior review found two guards whose prose
        # claimed more than their code delivered.
        assert "not a sandbox" in reason
        assert "false positive" in reason


# ---------------------------------------------------------------------------
# Direction 2: ordinary work is not blocked
# ---------------------------------------------------------------------------


class TestBashGuardAllows:
    @pytest.mark.parametrize(
        "command",
        [
            # read-only commands that MENTION a protected path — the biggest false-positive risk
            "grep -rn 'rm' discussions/",
            "grep -rn 'DELETE' metrics/evaluation.db",
            "cat discussions/2026-08-07/D/transcript.md",
            "ls -la discussions/2026-08-07",
            "head -5 .claude/settings.json",
            "wc -l discussions/2026-08-07/D/events.jsonl",
            "find discussions -name events.jsonl -size 0",
            "git log --oneline discussions/",
            "git status --porcelain discussions/",
            "git diff .claude/settings.json",
            "sed -n '1,20p' .claude/settings.json",
            # the repo's own measured sqlite3 usage: read-only SELECTs
            'sqlite3 metrics/evaluation.db "SELECT agent, COUNT(*) FROM turns GROUP BY agent;"',
            'sqlite3 metrics/evaluation.db "SELECT severity, category FROM findings LIMIT 20;"',
            # copying OUT of a protected path (source is only read)
            "cp metrics/evaluation.db /tmp/backup.db",
            "cp .claude/hooks/validate_tool_use.py /tmp/scratch.py",
            # ordinary framework work
            "python scripts/quality_gate.py",
            "python scripts/log_event.py --discussion DISC-1 --type critique",
            "python -m pytest tests/ -q",
            "ruff format .claude/hooks/validate_tool_use.py",
            "ruff check scripts/ --fix",
            "git commit -m 'feat: add guard'",
            "git checkout -b feat/new-thing",
            "rm -rf build/ dist/",
            "mv docs/draft.md docs/final.md",
            "echo done > /tmp/out.txt",
            "python -c \"print('hello')\"",
            "python -c \"open('/tmp/scratch.txt','w').write('x')\"",
            # read-only heredoc analysis over Layer 1 — exactly what a reviewer runs
            "python - <<'PY'\nimport pathlib\n"
            "print(sum(1 for _ in pathlib.Path('discussions').rglob('events.jsonl')))\nPY",
            "bash -c 'grep -rn DELETE discussions/'",
            # read-only pipelines over protected paths — the pipeline rule must not overreach
            "ls discussions/2026-08-07 | head -5",
            "git log --oneline discussions/ | wc -l",
            "find discussions -name events.jsonl | sort | uniq -c",
            "cat metrics/evaluation.db | head -c 16 | xxd",
            "grep -c DELETE discussions/2026-08-07/D/transcript.md | tee /tmp/count.txt",
            "",
            "   ",
        ],
    )
    def test_ordinary_command_is_allowed(self, command: str) -> None:
        assert _decision(command) is None, f"guard blocked ordinary work: {command!r}"

    @pytest.mark.parametrize(
        "command",
        [
            # /review, /deliberate, /analyze-project all do exactly this
            "python -c \"import json, pathlib; pathlib.Path('discussions/2026-08-07/D/state.json')"
            ".write_text(json.dumps({'command': 'review'}))\"",
            "python - <<'PY'\nimport json, pathlib\n"
            "state_path = pathlib.Path('discussions') / '2026-08-07' / 'D' / 'state.json'\n"
            "state_path.write_text(json.dumps({'phase': 'synthesis'}))\nPY",
        ],
    )
    def test_command_state_file_write_is_allowed(self, command: str) -> None:
        """MEASURED CORRECTION #2 — the guard must not break /review.

        Running an earlier draft over this repo's own fenced command blocks produced 6 DENY hits,
        all of them `state.json` writes in `.claude/commands/` —
        review.md, deliberate.md and analyze-project.md.
        A guard that hard-blocks `/review` is worse than no guard, because it gets switched off.
        """
        assert _decision(command) is None, f"guard would break a shipped command: {command!r}"

    def test_state_file_carve_out_does_not_cover_captured_reasoning(self) -> None:
        """The carve-out is state.json ONLY — transcripts and event logs stay protected."""
        assert (
            _decision(
                'python -c "import pathlib; '
                "pathlib.Path('discussions/2026-08-07/D/transcript.md').write_text('')\""
            )
            == "deny"
        )
        assert (
            _decision(
                'python -c "import pathlib; '
                "pathlib.Path('discussions/2026-08-07/D/state.json').unlink()\""
            )
            == "deny"
        )

    def test_env_example_is_not_treated_as_env(self) -> None:
        """.env.example is a committed template; overwriting it is routine."""
        assert _decision("cp .env.example.new .env.example") is None

    def test_github_directory_is_not_dot_git(self) -> None:
        assert _decision("rm -rf .github/workflows/stale.yml") is None


# ---------------------------------------------------------------------------
# The other shell — PowerShell and cmd.exe
# ---------------------------------------------------------------------------


class TestPowerShellAndCmdVerbs:
    """PowerShell is this repo's declared primary shell; cmd builtins reach the same files.

    The first draft of the guard enumerated POSIX verbs only, so the whole Windows dialect was a
    silent ALLOW. Both directions are tested here for the same reason they are tested for POSIX:
    the over-blocking failure mode ends with the guard switched off, which is the under-blocking
    failure mode with extra steps.
    """

    @pytest.mark.parametrize(
        "command",
        [
            # Remove-Item and its aliases / cmd equivalents
            r"Remove-Item -Recurse -Force discussions\2026-08-07",
            "Remove-Item discussions/2026-08-07/D/events.jsonl",
            "Remove-Item -Path discussions",
            "Remove-Item -LiteralPath metrics/evaluation.db",
            "ri discussions/2026-08-07",
            r"del discussions\2026-08-07\D\events.jsonl",
            "erase metrics/evaluation.db",
            "rd /s /q discussions",
            "rmdir /s /q discussions",
            # Move / rename — the source stops existing
            "Move-Item discussions/2026-08-07 C:/tmp/gone",
            "Move-Item -Path discussions/2026-08-07 -Destination C:/tmp/gone",
            "mi discussions/2026-08-07 C:/tmp/gone",
            "Rename-Item discussions/2026-08-07 C:/tmp/gone",
            # Writers that overwrite in place
            "Clear-Content discussions/2026-08-07/D/events.jsonl",
            "clc metrics/evaluation.db",
            "Set-Content discussions/2026-08-07/D/events.jsonl -Value ''",
            "Set-Content .claude/settings.json -Value '{}'",
            "'x' | Out-File metrics/evaluation.db",
            "Out-File -FilePath metrics/evaluation.db -InputObject 'x'",
            # Copy ONTO a protected path — including the reversed named-parameter order, which a
            # last-positional-argument rule reads backwards and lets through.
            "Copy-Item /tmp/f.db metrics/evaluation.db",
            "Copy-Item -Path /tmp/f.db -Destination metrics/evaluation.db",
            "Copy-Item -Destination metrics/evaluation.db -Path /tmp/f.db",
            "cpi /tmp/f.db metrics/evaluation.db",
            "xcopy C:/tmp/f.db metrics/evaluation.db",
            # Pipelines — the destroyed path is named upstream of the destructive stage
            "Get-ChildItem discussions/2026-08-07 | Remove-Item -Recurse -Force",
            # Hook and settings surfaces
            "Remove-Item -Recurse -Force .claude/hooks",
            r"Remove-Item -Force .git\index",
        ],
    )
    def test_windows_destructive_command_is_refused(self, command: str) -> None:
        assert _decision(command) == "deny", f"guard allowed a destructive command: {command!r}"

    @pytest.mark.parametrize(
        "command",
        [
            # read-only cmdlets that MENTION a protected path
            "Get-Content discussions/2026-08-07/D/events.jsonl",
            "Get-ChildItem discussions/2026-08-07",
            "Select-String -Pattern DELETE -Path discussions/2026-08-07/D/transcript.md",
            "Test-Path metrics/evaluation.db",
            "Get-ChildItem discussions | Measure-Object",
            # ordinary destructive work on UNprotected paths
            "Remove-Item -Recurse -Force build/",
            "Remove-Item C:/tmp/scratch.txt",
            "del C:/tmp/junk.txt",
            "Move-Item docs/draft.md docs/final.md",
            "Rename-Item docs/old.md docs/new.md",
            # copying OUT of a protected path — the source is only read
            "Copy-Item metrics/evaluation.db C:/tmp/backup.db",
            "Copy-Item -Path metrics/evaluation.db -Destination C:/tmp/backup.db",
            # ``Add-Content`` onto an UNprotected path stays ordinary work
            "Add-Content notes/log.md -Value '{}'",
            # ``sc`` is also sc.exe (service control); its operands are never paths
            "sc query winrm",
        ],
    )
    def test_ordinary_windows_command_is_allowed(self, command: str) -> None:
        assert _decision(command) is None, f"guard blocked ordinary work: {command!r}"

    @pytest.mark.parametrize(
        "command",
        [
            "Set-Content notes.md -Value 'see discussions/2026-08-07 for context'",
            "Set-Content -Path notes.md -Value 'rm -rf discussions/'",
            "Out-File -FilePath C:/tmp/out.txt -InputObject 'metrics/evaluation.db'",
        ],
    )
    def test_parameter_values_are_data_not_paths(self, command: str) -> None:
        """``-Value``/``-InputObject`` carry CONTENT. Treating content as a path over-blocks.

        Writing a note that merely quotes a protected path is ordinary work, and a guard that
        refuses it teaches the developer to switch the guard off.
        """
        assert _decision(command) is None, f"guard treated content as a path: {command!r}"

    def test_new_item_is_deliberately_not_matched(self) -> None:
        """Documented limit, asserted so it cannot drift into an unexamined belief.

        ``New-Item -ItemType Directory -Force`` is the PowerShell ``mkdir -p``; POSIX ``mkdir`` is
        unmatched too. Matching it would refuse routine directory creation under ``discussions/``.
        The module docstring's CANNOT list names this; this test is that sentence's receipt.
        """
        assert _decision("New-Item -ItemType Directory -Force discussions/2026-08-08") is None

    def test_new_item_file_form_is_matched_and_directory_form_is_not(self) -> None:
        """``New-Item`` is two commands wearing one name; only one of them is ordinary work.

        The earlier draft allowed both on the strength of the DIRECTORY half of the rationale
        (``New-Item -ItemType Directory -Force`` is the PowerShell ``mkdir -p``). But the FILE
        form overwrites an existing file with an empty one — a truncation primitive of exactly
        the incident class (``: > …/events.jsonl``), whose POSIX analogue is not ``mkdir`` but
        ``> file``, which this guard already matches. MEASURED: ``grep -rn 'New-Item'`` over
        ``.claude/{commands,skills,rules,agents}``, ``scripts/`` and ``CLAUDE.md`` → 0 hits, so
        matching the file form costs no documented workflow.
        """
        assert _decision("New-Item -Force discussions/2026-08-07/D/events.jsonl") == "deny"
        assert (
            _decision("New-Item -ItemType File -Force discussions/2026-08-07/D/events.jsonl")
            == "deny"
        )
        assert _decision("ni -ItemType File -Force metrics/evaluation.db") == "deny"
        # The directory form remains ordinary work — refusing it would block routine capture.
        assert _decision("New-Item -ItemType Directory -Force discussions/2026-08-08") is None
        assert _decision("New-Item -ItemType Directory -Force build/out") is None

    def test_dotnet_and_iex_shapes_are_documented_as_unmatched(self) -> None:
        """Honest-limit test: these are NOT caught, and the docstring says so.

        If a later change starts catching them, this test fails and the docstring's CANNOT list
        must be corrected in the same commit — the point is that code and prose move together.
        """
        assert (
            _decision("[System.IO.File]::Delete('discussions/2026-08-07/D/events.jsonl')") is None
        )
        assert _decision("iex $cmd") is None


# ---------------------------------------------------------------------------
# Wrapper shells — the payload must be unwrapped and re-checked
# ---------------------------------------------------------------------------


class TestWrapperShellUnwrapping:
    """``powershell -Command '<payload>'`` was a one-word bypass of the entire guard.

    This is the most serious defect the second review found, and it is worse than it looks on
    paper: **this machine's primary shell tool is PowerShell.** The orchestrating session runs
    commands through it constantly, so the guard was routed around by the single most natural way
    to run anything here. The verb table added for PowerShell in the previous round did not help,
    because the destructive verb was sitting inside a quoted argument to ``powershell`` and the
    only command word the parser ever saw was ``powershell`` itself.
    """

    @pytest.mark.parametrize(
        "command",
        [
            # powershell -Command, in the spellings people actually type
            'powershell -Command "Clear-Content discussions/2026-08-07/D/events.jsonl"',
            "powershell -Command 'Remove-Item -Recurse -Force discussions/2026-08-07'",
            "pwsh -c 'Remove-Item -Recurse -Force discussions'",
            "pwsh -Command 'rm -rf discussions/2026-08-07'",
            'powershell.exe -NoProfile -Command "rm -rf discussions/2026-08-07"',
            # intervening flags, including one that takes a value
            'powershell -NoProfile -NonInteractive -Command "rm -rf discussions"',
            'powershell -ExecutionPolicy Bypass -Command "Clear-Content metrics/evaluation.db"',
            # the inner payload's own quoting must survive unwrapping
            'powershell -Command "sqlite3 metrics/evaluation.db \\"DELETE FROM findings\\""',
            # cmd.exe — the case the docstring previously admitted was unmatched
            'cmd /c "del discussions\\2026-08-07\\D\\events.jsonl"',
            "cmd.exe /c rd /s /q discussions",
            "cmd /k rmdir /s /q discussions",
            # POSIX wrappers (pre-existing coverage, kept)
            "bash -c 'rm -rf discussions/2026-08-07'",
            'sh -c ": > metrics/evaluation.db"',
            "bash -e -c 'rm -rf discussions'",
            # a wrapper inside a wrapper
            "bash -c \"powershell -Command 'Remove-Item -Recurse discussions'\"",
        ],
    )
    def test_wrapped_destructive_payload_is_refused(self, command: str) -> None:
        assert _decision(command) == "deny", f"wrapper bypass still open: {command!r}"

    @pytest.mark.parametrize(
        "command",
        [
            'powershell -Command "Get-Content discussions/2026-08-07/D/events.jsonl"',
            "pwsh -c 'Get-ChildItem discussions | Measure-Object'",
            'cmd /c "dir discussions"',
            "bash -c 'grep -rn DELETE discussions/'",
            'powershell -Command "python -m pytest tests/ -q"',
            'powershell -Command "Remove-Item -Recurse -Force build/"',
        ],
    )
    def test_wrapped_readonly_payload_is_allowed(self, command: str) -> None:
        """Unwrapping must not turn every wrapper invocation into a refusal.

        The payload is re-checked with the SAME rules, so a read-only payload stays allowed. If
        this direction broke, every ``powershell -Command`` on the machine would be refused and
        the guard would be switched off within the hour.
        """
        assert _decision(command) is None, f"guard blocked ordinary work: {command!r}"

    def test_encoded_command_is_decoded_and_rechecked(self) -> None:
        """``-EncodedCommand`` is base64 (UTF-16LE). Decoding it is the honest option.

        The alternative considered was denying the flag outright against protected paths. That
        was rejected: an encoded command touching nothing protected is ordinary work, and a guard
        that refuses a whole flag on sight is the kind that gets switched off. Decoding buys
        exactly one layer — the decoded text then gets the same text matching as anything else,
        which the docstring's CANNOT list states rather than glossing.
        """
        destructive = "Remove-Item -Recurse -Force discussions/2026-08-07"
        blob = base64.b64encode(destructive.encode("utf-16-le")).decode()
        assert _decision(f"powershell -EncodedCommand {blob}") == "deny"
        assert _decision(f"pwsh -enc {blob}") == "deny"
        assert _decision(f"powershell -e {blob}") == "deny"

        benign = base64.b64encode("Get-ChildItem build".encode("utf-16-le")).decode()
        assert _decision(f"powershell -EncodedCommand {benign}") is None

    def test_undecodable_encoded_command_asks_and_says_it_could_not_read_it(self) -> None:
        """An unreadable payload must not silently pass as if it had been inspected."""
        verdict = hook.check_bash_command("powershell -EncodedCommand @@@notbase64@@@")
        assert verdict is None or verdict[0] == "ask"
        # Valid base64, but decodes as neither UTF-16LE (odd byte count) nor UTF-8 (0xFF).
        blob = base64.b64encode(bytes([0xFF, 0xFE, 0x80])).decode()
        verdict = hook.check_bash_command(f"powershell -EncodedCommand {blob}")
        assert verdict is not None and verdict[0] == "ask"
        assert "could not be decoded" in verdict[1]
        assert "not because it" in verdict[1]  # "…not because it was judged safe"

    def test_execution_policy_flag_is_not_mistaken_for_encodedcommand(self) -> None:
        """``-ExecutionPolicy`` starts with ``-e``; misreading it would corrupt the unwrap.

        Regression guard for the flag-collision that made per-family patterns necessary in the
        first place (``bash -e -c`` had the same shape).
        """
        assert (
            _decision('powershell -ExecutionPolicy Bypass -Command "Get-ChildItem build"') is None
        )

    def test_unwrapping_can_fail_when_the_powershell_pattern_is_disabled(self) -> None:
        """Prove the unwrap tests are load-bearing, not passing for some other reason."""
        original = hook._PS_COMMAND_RE
        try:
            hook._PS_COMMAND_RE = re.compile(r"(?!x)x")  # matches nothing
            assert (
                _decision('powershell -Command "Clear-Content discussions/2026-08-07/D/e.jsonl"')
                is None
            ), "expected the pre-fix bypass once unwrapping is disabled"
        finally:
            hook._PS_COMMAND_RE = original
        assert (
            _decision('powershell -Command "Clear-Content discussions/2026-08-07/D/e.jsonl"')
            == "deny"
        )


# ---------------------------------------------------------------------------
# Relative paths and the shell's working directory
# ---------------------------------------------------------------------------


class TestWorkingDirectoryResolution:
    """A relative path after a ``cd`` names nothing protected in its own text.

    The previous suite contained a passing ``cd /tmp && rm -rf discussions/...`` DENY case, which
    read as evidence that ``cd`` chains were handled. They were not — that case passed because the
    ``rm`` stage still spelled out ``discussions/`` itself. These tests separate the two.
    """

    @pytest.mark.parametrize(
        "command",
        [
            "cd discussions/2026-08-07 && rm -rf DISC-1",
            "cd discussions && rm -rf .",
            "cd metrics && rm evaluation.db",
            "cd discussions/2026-08-07; rm -rf DISC-1/events.jsonl",
            "cd .claude && rm -rf hooks",
            "cd metrics && sqlite3 evaluation.db 'DELETE FROM findings'",
            # ``..`` must be resolved, not treated as a literal component
            "cd docs/../discussions && rm -rf 2026-08-07",
            # PowerShell spelling
            "Set-Location discussions/2026-08-07; Remove-Item -Recurse -Force DISC-1",
        ],
    )
    def test_relative_path_after_cd_is_resolved(self, command: str) -> None:
        assert _decision(command) == "deny", f"cd-relative bypass still open: {command!r}"

    def test_cd_into_an_unrelated_directory_does_not_manufacture_hits(self) -> None:
        """Resolution must not deny ordinary work that merely happens to follow a ``cd``."""
        assert _decision("cd docs && rm -rf drafts") is None
        assert _decision("cd build && rm -rf out") is None
        assert _decision("cd src && ls -la") is None

    def test_the_across_calls_case_is_not_caught_and_that_is_disclosed(self) -> None:
        """HONEST-LIMIT TEST. This is the hole that cannot be closed from command text.

        Both the ``Bash`` and ``PowerShell`` tools on this machine document that the working
        directory persists between calls. So ``cd discussions/2026-08-07`` in one call and
        ``rm -rf DISC-1`` in the NEXT call defeats the guard completely: a PreToolUse hook sees
        one command at a time and has no memory of the shell's state.

        This test asserts the miss ON PURPOSE, and binds it to the prose: if a future change
        starts catching it, this test fails and the docstring + education row must be corrected
        in the same commit. A hole that is disclosed is survivable; one that is silently believed
        closed is not.
        """
        assert _decision("rm -rf DISC-1") is None
        assert _decision("rm -rf 2026-08-07") is None

        # Whitespace-normalized so a line wrap in the prose cannot silently void the assertion.
        docstring = " ".join((hook.__doc__ or "").split())
        assert "working directory persists between calls" in docstring
        assert "cannot be, from command text alone" in docstring

        education = " ".join(
            (REPO_ROOT / "docs" / "education" / "governance-mechanisms.md")
            .read_text(encoding="utf-8")
            .split()
        )
        assert "persists between calls" in education, "the education row must disclose this too"


# ---------------------------------------------------------------------------
# Inline python — the write must TARGET the protected path, not merely co-occur with it
# ---------------------------------------------------------------------------

# The six read-only shapes an earlier draft of the inline-python rule denied. Each is paired with
# the SHELL spelling of the same act, which that draft allowed — the disagreement between the two
# spellings is the defect, not a matter of taste.
READ_ONLY_INLINE_PYTHON = [
    # 1. The copy-the-DB-to-a-scratch-path idiom this repo's own task briefs mandate so that
    #    analysis never touches Layer 2. Shell twin: `cp metrics/evaluation.db /tmp/backup.db`.
    "python -c \"import shutil; shutil.copy('metrics/evaluation.db','/tmp/scratch.db')\"",
    # 2. The mandated READ-ONLY URI connection — denied for where it wrote its report.
    'python -c "import sqlite3,json; '
    "rows=sqlite3.connect('file:metrics/evaluation.db?mode=ro', uri=True)"
    ".execute('SELECT 1').fetchall(); open('/tmp/o.json','w').write(json.dumps(rows))\"",
    # 3. The same, via csv.writer.
    'python -c "import sqlite3,csv; '
    "rows=sqlite3.connect('file:metrics/evaluation.db?mode=ro', uri=True)"
    ".execute('SELECT 1').fetchall(); csv.writer(open('/tmp/o.csv','w')).writerows(rows)\"",
    # 4. Denied for writing to STDOUT.
    "python -c \"import sys; sys.stdout.write(open('discussions/a/events.jsonl').read())\"",
    # 5/6. Counting files under discussions/ and writing the COUNT to /tmp, both spellings.
    "python -c \"import pathlib; open('/tmp/out.txt','w')"
    ".write(str(len(list(pathlib.Path('discussions').rglob('*')))))\"",
    "python - <<'PY'\nimport pathlib\nopen('/tmp/out.txt','w')"
    ".write(str(len(list(pathlib.Path('discussions').rglob('*')))))\nPY",
]


@pytest.mark.regression
class TestInlinePythonWritesAreAttributedToTheirTarget:
    """MEASURED FALSE-POSITIVE CLASS — the inline-python rule denied read-only analysis.

    The rule fired when a command was inline python AND contained a write/destroy verb anywhere
    AND *mentioned* a protected path anywhere. It never checked that the write TARGETED the
    protected path, so all six shapes above returned ``deny`` — including the DB-copy-to-scratch
    idiom this repo's own task briefs mandate, and a ``mode=ro`` connection denied for writing its
    report to ``/tmp``. Their shell twins were all ALLOWED, so one act had two spellings that
    disagreed, in the one branch where ``deny`` has no in-session override.

    This is the guard's own stated failure mode — "blocks ordinary work → gets switched off →
    same as no guard" — so both directions are pinned here.
    """

    @pytest.mark.parametrize("command", READ_ONLY_INLINE_PYTHON)
    def test_read_only_inline_python_is_allowed(self, command: str) -> None:
        assert _decision(command) is None, f"unrecoverable false positive: {command!r}"

    @pytest.mark.parametrize(
        ("inline_python", "shell_twin"),
        [
            (READ_ONLY_INLINE_PYTHON[0], "cp metrics/evaluation.db /tmp/backup.db"),
            (READ_ONLY_INLINE_PYTHON[0], "Copy-Item metrics/evaluation.db C:/tmp/backup.db"),
            (READ_ONLY_INLINE_PYTHON[4], "ls discussions | wc -l > /tmp/out.txt"),
        ],
    )
    def test_the_two_spellings_of_one_act_agree(self, inline_python: str, shell_twin: str) -> None:
        """The defect was not "too strict" in the abstract — it was INCONSISTENT.

        The shell spelling of each act was allowed (``cp metrics/evaluation.db /tmp/backup.db`` is
        pinned as allowed elsewhere in this file). A guard whose verdict depends on which language
        you wrote the same read in teaches exactly one lesson: route around the guard.
        """
        assert _decision(inline_python) == _decision(shell_twin)

    @pytest.mark.parametrize(
        "command",
        [
            # the incident shape, in python
            "python -c \"open('discussions/2026-08-07/D/events.jsonl','w').close()\"",
            "python -c \"open('metrics/evaluation.db','wb').write(b'')\"",
            # the path is the RECEIVER, not an argument
            'python -c "import pathlib; '
            "pathlib.Path('discussions/a/events.jsonl').write_text('')\"",
            # ``.open('w')`` puts the mode in a DIFFERENT slot than builtin ``open``
            'python -c "import pathlib; '
            "pathlib.Path('discussions/a/events.jsonl').open('w').write('')\"",
            # copying ONTO a protected path — the destination argument, not the source
            "python -c \"import shutil; shutil.copy('/tmp/f.db','metrics/evaluation.db')\"",
            "python -c \"import shutil; shutil.move('discussions/2026-08-07','/tmp/gone')\"",
            "python -c \"import os; os.remove('discussions/a/events.jsonl')\"",
            # rename NAMES BOTH ENDS — the protected path is the second argument
            "python -c \"import os; os.rename('/tmp/x','discussions/a/events.jsonl')\"",
            "python -c \"import os; os.truncate('metrics/evaluation.db', 0)\"",
            # a path spelled in pieces must still join back up
            'python -c "import os,shutil; '
            "shutil.rmtree(os.path.join('discussions','2026-08-07'))\"",
            'python -c "import pathlib; '
            "(pathlib.Path('discussions') / 'a' / 'events.jsonl').write_text('')\"",
            # the file handle is a variable — the ``open`` that created it is what gets matched
            "python -c \"f=open('discussions/a/events.jsonl','w'); f.write('')\"",
            "python -c \"import pathlib; pathlib.Path('.claude/settings.json').write_text('{}')\"",
            "python -c \"import io; io.open('metrics/evaluation.db','w').close()\"",
        ],
    )
    def test_a_write_that_really_targets_a_protected_path_still_denies(self, command: str) -> None:
        """Narrowing must not have bought its false-positive fix with a false-negative hole."""
        assert _decision(command) == "deny", f"narrowing lost real coverage: {command!r}"

    def test_the_review_shaped_bare_name_receiver_is_resolved_one_hop(self) -> None:
        """``p = Path(...)`` then ``p.write_text(...)`` — the shape ``/review`` itself uses.

        A bare-name receiver carries no literal of its own. It is resolved ONE hop through its
        assignment, which is what lets the ``state.json`` carve-out apply to the ``/review``
        heredoc AND what keeps the same shape denied when it names ``events.jsonl``.
        """
        events = (
            "python - <<'PY'\nimport pathlib\n"
            "p = pathlib.Path('discussions') / 'a' / 'events.jsonl'\np.write_text('')\nPY"
        )
        state = (
            "python - <<'PY'\nimport pathlib, json\n"
            "p = pathlib.Path('discussions') / '2026-08-07' / 'D' / 'state.json'\n"
            "p.write_text(json.dumps({'phase': 'synthesis'}))\nPY"
        )
        assert _decision(events) == "deny"
        assert _decision(state) is None

    def test_an_unattributable_target_asks_and_says_it_could_not_read_it(self) -> None:
        """``ask`` here means UNATTRIBUTED, not judged-safe — the opaque-SQL branch's own word.

        A destructive call whose operand is a loop variable or ``sys.argv[1]`` cannot be tied to a
        path from the text. Denying it would resurrect the false-positive class; allowing it
        silently would be the co-occurrence rule's opposite error.
        """
        verdict = hook.check_bash_command(
            'python -c "import pathlib; '
            "[f.unlink() for f in pathlib.Path('discussions').rglob('*')]\""
        )
        assert verdict is not None and verdict[0] == "ask"
        assert "could not be read from the text" in verdict[1]

    def test_an_unattributable_target_with_nothing_protected_in_scope_is_allowed(self) -> None:
        """The ask is scoped to programs that actually name a protected path."""
        assert _decision('python -c "import sys,shutil; shutil.rmtree(sys.argv[1])"') is None

    @pytest.mark.parametrize(
        "command",
        [
            # the ARGUMENT of write_text is CONTENT, exactly like PowerShell's -Value
            'python -c "import pathlib; '
            "pathlib.Path('/tmp/o.md').write_text('see discussions/2026-08-07')\"",
            # str.replace must never be read as os.replace — bare names are excluded on purpose
            "python -c \"s='discussions/x'; print(s.replace('discussions','d'))\"",
            # reading Layer 1 and writing the REPORT elsewhere
            "python -c \"open('/tmp/r.md','w')"
            ".write(open('discussions/a/transcript.md').read())\"",
            'python -c "import pathlib; '
            "print(sorted(p.name for p in pathlib.Path('discussions').iterdir()))\"",
        ],
    )
    def test_content_and_read_operands_are_not_treated_as_write_targets(
        self, command: str
    ) -> None:
        assert _decision(command) is None, f"guard blocked ordinary work: {command!r}"

    def test_attribution_is_what_carries_this_not_something_else(self) -> None:
        """Prove the deny cases above are load-bearing on the op tables, not passing by accident.

        Empty the python op tables and the inline-python denies must collapse to the
        unattributed-``ask`` floor (or to allow) — reproducing, in-suite, a guard that cannot see
        python writes at all.
        """
        targeted = "python -c \"import shutil; shutil.copy('/tmp/f.db','metrics/evaluation.db')\""
        assert _decision(targeted) == "deny"
        original_arg, original_method = hook._PY_ARG_OPS, hook._PY_METHOD_OPS
        try:
            hook._PY_ARG_OPS, hook._PY_METHOD_OPS = {}, {}
            assert _decision(targeted) != "deny", "expected the table-less hole"
        finally:
            hook._PY_ARG_OPS, hook._PY_METHOD_OPS = original_arg, original_method
        assert _decision(targeted) == "deny"

    @pytest.mark.parametrize(
        "command",
        [
            # os.open + os.write: a file descriptor, not the builtin ``open`` this guard knows
            "python -c \"import os; fd=os.open('discussions/a/events.jsonl', os.O_WRONLY); "
            "os.write(fd,b'')\"",
            # a writer that is not ``open``
            "python -c \"import zipfile; zipfile.ZipFile('metrics/evaluation.db','w')\"",
            # aliased and bare-name imports — bare names are excluded on purpose (str.replace)
            "python -c \"import shutil as sh; sh.rmtree('discussions/2026-08-07')\"",
            "python -c \"from shutil import rmtree; rmtree('discussions/2026-08-07')\"",
        ],
    )
    def test_the_enumeration_gaps_are_asserted_not_merely_admitted(self, command: str) -> None:
        """HONEST-LIMIT TEST — these are NOT caught, and both prose surfaces say so.

        The python op tables are a closed enumeration exactly like the shell verb tables, and the
        same rule applies: a limit that is written down but never asserted quietly becomes a
        belief. If a future change starts catching any of these, this test fails and the
        docstring + education leak 5 must be corrected in the same commit.
        """
        assert _decision(command) is None

    def test_the_false_positive_class_is_disclosed_in_the_docstring(self) -> None:
        """Code and prose move together — the fix is only trustworthy if its limits are written.

        ``deny`` has no in-session override, so an undisclosed false-positive class is a trap.
        """
        docstring = " ".join((hook.__doc__ or "").split())
        assert "does not target the protected path" in docstring
        assert "CO-OCCURRENCE" in docstring
        assert "shutil.copy('metrics/evaluation.db', '/tmp/scratch.db')" in docstring
        assert "unresolved" in docstring


# ---------------------------------------------------------------------------
# Path matching precision — false positives have no override
# ---------------------------------------------------------------------------


class TestPathComponentMatching:
    """``deny`` has no in-session override, so a false positive is unrecoverable.

    Matching moved from substring containment to whole path components. Measured: this repo has
    exactly one directory named ``discussions``
    (``find . -type d -name discussions -not -path './.claude/worktrees/*'`` → ``./discussions``),
    so the tightening costs no real coverage here.
    """

    @pytest.mark.parametrize(
        "command",
        [
            "rm -rf my-discussions-notes/",
            "rm -rf notes/old-discussions-archive",
            "rm /tmp/scratch-metrics/evaluation.db",
            "rm backups/metrics/evaluation.db.2026-08-01.bak",
            "rm -rf build/.git-cache-x/tmp",
            "rm -rf .github/workflows/stale.yml",
            "rm .env.example",
        ],
    )
    def test_unrelated_lookalike_paths_are_not_denied(self, command: str) -> None:
        assert _decision(command) is None, f"unrecoverable false positive: {command!r}"

    @pytest.mark.parametrize(
        "command",
        [
            "rm -rf discussions",
            "rm -rf discussions/",
            "rm -rf ./discussions/2026-08-07",
            "rm -rf C:/repo/discussions/2026-08-07",
            r"rm -rf C:\repo\discussions\2026-08-07",
            "rm metrics/evaluation.db",
            "rm -rf .claude/hooks",
        ],
    )
    def test_real_protected_paths_still_match(self, command: str) -> None:
        assert _decision(command) == "deny", f"tightening lost real coverage: {command!r}"

    def test_deny_reason_names_the_matched_token(self) -> None:
        """A false positive is only recoverable if a human can SEE what matched."""
        verdict = hook.check_bash_command("rm -rf discussions/2026-08-07")
        assert verdict is not None
        assert "discussions/2026-08-07" in verdict[1]
        assert "NO in-session override" in verdict[1]


# ---------------------------------------------------------------------------
# Appending — the one decision that had no measurement behind it
# ---------------------------------------------------------------------------


class TestAppendConsistency:
    """The ``>>``-into-``discussions/`` carve-out was removed. Three appenders now agree.

    It was the only design decision in this guard with no measurement behind it, and it was
    inconsistent three ways: ``tee -a`` denied, ``Add-Content`` allowed only because nobody had
    listed it, and the Write/Edit half of this same validator denies
    ``discussions/**/events.jsonl`` unconditionally — so the shell half was strictly WEAKER than
    the file half on the one file the file half exists to protect.

    MEASURED before removal: ``grep -rnE '>>\\s*[^ ]*discussions/' .claude/ scripts/ CLAUDE.md
    docs/`` → 0 hits. The carve-out protected no workflow.
    """

    @pytest.mark.parametrize(
        "command",
        [
            "echo '{\"e\":1}' >> discussions/2026-08-07/D/events.jsonl",
            "echo '{}' | tee -a discussions/2026-08-07/D/events.jsonl",
            "Add-Content discussions/2026-08-07/D/events.jsonl -Value '{}'",
        ],
    )
    def test_all_three_appenders_agree(self, command: str) -> None:
        assert _decision(command) == "deny", f"appender inconsistency remains: {command!r}"

    def test_the_sanctioned_appender_is_unaffected(self) -> None:
        """``scripts/log_event.py`` is a program invocation, not a redirect — it never matched."""
        assert _decision("python scripts/log_event.py --discussion DISC-1 --type critique") is None

    def test_shell_half_is_now_at_least_as_strict_as_the_write_half(self) -> None:
        """The specific inversion that made the carve-out indefensible."""
        events = "discussions/2026-08-07/DISC-1/events.jsonl"
        assert hook.is_append_only_log(events) is True  # Write/Edit half denies
        assert _decision(f"echo x >> {events}") == "deny"  # shell half now denies too


# ---------------------------------------------------------------------------
# SQL the guard cannot read
# ---------------------------------------------------------------------------


class TestOpaqueSqlScripts:
    """``sqlite3 db < wipe.sql`` supplies statements from a file this hook never opens."""

    @pytest.mark.parametrize(
        "command",
        [
            "sqlite3 metrics/evaluation.db < wipe.sql",
            "sqlite3 metrics/evaluation.db < scripts/migrate.sql",
            'sqlite3 metrics/evaluation.db ".read wipe.sql"',
            'sqlite3 metrics/evaluation.db ".import data.csv findings"',
        ],
    )
    def test_sql_from_a_file_asks_because_it_cannot_be_read(self, command: str) -> None:
        """ASK means UNREAD, not judged-safe — and the reason must say which.

        MEASURED: zero uses of either shape in ``.claude/{commands,skills,rules,agents}``,
        ``scripts/`` or ``CLAUDE.md``, so asking costs no documented workflow. Denying was
        rejected because the script may be a read-only report.
        """
        verdict = hook.check_bash_command(command)
        assert verdict is not None, f"opaque SQL passed silently: {command!r}"
        assert verdict[0] == "ask"
        assert "text unread" in verdict[1]

    @pytest.mark.parametrize(
        "command",
        [
            # a ``<`` inside SQL text is a comparison, not a redirection
            'sqlite3 metrics/evaluation.db "SELECT * FROM turns WHERE cost < 5"',
            # heredocs are a different shape and already handled by the inline-python rules
            "sqlite3 /tmp/scratch.db < wipe.sql",
        ],
    )
    def test_comparison_operators_and_unprotected_dbs_are_not_flagged(self, command: str) -> None:
        assert _decision(command) is None, f"false positive on opaque-SQL detection: {command!r}"


# ---------------------------------------------------------------------------
# Existing protected-file behaviour (finding M4: previously untested)
# ---------------------------------------------------------------------------


class TestProtectedPatterns:
    @pytest.mark.parametrize(
        "path",
        [
            ".git/config",
            "/repo/.git/hooks/pre-commit",
            ".env",
            "/repo/.env",
            "metrics/evaluation.db",
            r"C:\repo\metrics\evaluation.db",
            ".claude/settings.json",
        ],
    )
    def test_protected_paths_are_protected(self, path: str) -> None:
        assert hook.is_protected(path) is True

    @pytest.mark.parametrize(
        "path", ["src/main.py", "docs/adr/ADR-0001.md", "metrics/quality_gate_log.jsonl"]
    )
    def test_ordinary_paths_are_not_protected(self, path: str) -> None:
        assert hook.is_protected(path) is False

    @pytest.mark.parametrize(
        "path",
        [
            "discussions/2026-08-07/DISC-1/events.jsonl",
            r"discussions\2026-08-07\DISC-1\events.jsonl",
            "/repo/discussions/2026-01-01/DISC-2/events.jsonl",
        ],
    )
    def test_append_only_logs_are_detected(self, path: str) -> None:
        assert hook.is_append_only_log(path) is True

    @pytest.mark.parametrize(
        "path",
        [
            "discussions/2026-08-07/DISC-1/transcript.md",
            "discussions/2026-08-07/DISC-1/artifacts/notes.md",
            "metrics/events.jsonl.bak",
        ],
    )
    def test_non_layer1_logs_are_writable(self, path: str) -> None:
        assert hook.is_append_only_log(path) is False


# ---------------------------------------------------------------------------
# The real hook protocol
# ---------------------------------------------------------------------------


class TestEndToEndHookProtocol:
    def test_write_to_protected_file_denies(self) -> None:
        result = _run_hook(
            {
                "tool_name": "Write",
                "session_id": "t",
                "tool_input": {"file_path": "metrics/evaluation.db", "content": "x"},
            }
        )
        assert result is not None
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_write_to_events_jsonl_denies(self) -> None:
        result = _run_hook(
            {
                "tool_name": "Write",
                "session_id": "t",
                "tool_input": {
                    "file_path": "discussions/2026-08-07/DISC-1/events.jsonl",
                    "content": "{}",
                },
            }
        )
        assert result is not None
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "append-only" in result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_ordinary_bash_command_emits_no_decision(self) -> None:
        assert _run_hook({"tool_name": "Bash", "tool_input": {"command": "ls -la"}}) is None

    def test_malformed_stdin_does_not_block(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input="not json",
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=30,
        )
        assert proc.returncode == 0
        assert proc.stdout.strip() == ""

    def test_bash_payload_without_tool_name_is_still_guarded(self) -> None:
        """Robustness: some hook payloads omit tool_name; the command field is enough."""
        result = _run_hook({"tool_input": {"command": INCIDENT_TRUNCATE}})
        assert result is not None
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


# ---------------------------------------------------------------------------
# Load-bearing floor — verified independently before this round's changes began
# ---------------------------------------------------------------------------


@pytest.mark.regression
class TestVerifiedBaselineMustNotRegress:
    """Four behaviours confirmed working by hand BEFORE this round of fixes.

    Everything else in this file is new or changed. This class is the floor: the fixes for the
    PowerShell bypass, ``cd`` resolution and the append carve-out all widened what the guard
    refuses, and widening a refusal set is exactly how a guard starts blocking ordinary work and
    gets switched off. These four pin both directions of that risk in one place.
    """

    def test_the_exact_incident_command_is_denied(self) -> None:
        result = _run_hook({"tool_name": "Bash", "tool_input": {"command": INCIDENT_TRUNCATE}})
        assert result is not None
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    @pytest.mark.parametrize(
        "file_path",
        ["discussions/2026-08-07/DISC-1/events.jsonl", ".claude/settings.json"],
    )
    def test_write_to_protected_path_is_denied(self, file_path: str) -> None:
        result = _run_hook(
            {
                "tool_name": "Write",
                "session_id": "t",
                "tool_input": {"file_path": file_path, "content": "x"},
            }
        )
        assert result is not None
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    @pytest.mark.parametrize("command", ["ls -la", "python -m pytest"])
    def test_ordinary_command_emits_no_decision_through_the_real_hook(self, command: str) -> None:
        assert _run_hook({"tool_name": "Bash", "tool_input": {"command": command}}) is None
        assert _run_hook({"tool_name": "PowerShell", "tool_input": {"command": command}}) is None


# ---------------------------------------------------------------------------
# Prose must not outrun code
# ---------------------------------------------------------------------------


class TestEducationRowMatchesTheCode:
    """The education row and the code must state the SAME strength for ``ask``.

    This repo already carried two guards whose prose overstated their code. The previous version
    of the education row said ``ask`` means "the command is paused and handed to you to approve"
    — a stronger guarantee than the code's own comment, which says ``ask`` has not been verified
    under ``--permission-mode bypassPermissions`` and should be treated as "probably stops it".
    The overclaim sat in the one artifact whose stated purpose is that a row without its weakness
    gets believed further than it deserves.

    These assertions are deliberately about PROSE. The best catch of the previous two review waves
    was an unmeasured prose claim in a document whose every code block had been verified.
    """

    @staticmethod
    def _education() -> str:
        path = REPO_ROOT / "docs" / "education" / "governance-mechanisms.md"
        return " ".join(path.read_text(encoding="utf-8").split())

    def test_the_code_still_hedges_ask(self) -> None:
        """If the code ever stops hedging, the doc below must be revisited, not silently kept."""
        source = HOOK_PATH.read_text(encoding="utf-8")
        assert "probably stops it" in source
        assert "bypassPermissions" in source

    def test_the_row_states_the_ask_weakness_where_it_states_ask(self) -> None:
        education = self._education()
        assert "probably stops it" in education, "the row must carry the code's own hedge"
        assert "bypassPermissions" in education
        assert "session_supervisor.py" in education

    @staticmethod
    def _table_row(prefix: str) -> str:
        """The single decision-table row starting with ``| **deny**`` / ``| **ask**``."""
        path = REPO_ROOT / "docs" / "education" / "governance-mechanisms.md"
        rows = [
            line
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip().startswith(f"| **{prefix}**")
        ]
        assert len(rows) == 1, f"expected exactly one '{prefix}' table row, found {len(rows)}"
        return rows[0]

    def test_the_ask_table_row_carries_the_weakness_in_the_same_breath(self) -> None:
        """Finding M1, pinned at the exact place it went wrong: the ROW, not the surrounding prose.

        An earlier attempt at this test searched the whole document for the old sentence — which
        false-fired, because the document now legitimately *quotes* the old claim in order to
        explain why it was wrong. The row itself is the thing the reader explains back, so the
        row itself is what must carry the caveat.
        """
        row = self._table_row("ask")
        assert "probably stops it" in row, "the ask row must carry the code's own hedge"
        assert "bypassPermissions" in row, "the row must name the session type that breaks ask"

    def test_the_deny_table_row_states_that_there_is_no_override(self) -> None:
        row = self._table_row("deny")
        assert "no override" in row

    def test_the_row_names_the_wrapper_bypass_and_the_activation_gap(self) -> None:
        education = self._education()
        assert "powershell -Command" in education, "the wrapper bypass must be named"
        assert "Bash|PowerShell" in education, "the wiring the guard is inert without"

    def test_the_row_names_every_checkout_the_bypass_is_still_open_in(self) -> None:
        """The activation gap is not one file — it is five checkouts, and the row must say so.

        Measured read-only on 2026-08-07: all four derived projects carry a ~232-line validator
        with no shell guard at all, and ``dan_research_karpathy_wiki`` has NO ``PreToolUse`` key
        at all, so its validator does not run even on ``Write``/``Edit``. An earlier draft of this
        row said all four were wired ``Write|Edit``-only; that was asserted rather than measured,
        and it was wrong about the fourth. A later draft called the fourth an "empty ``PreToolUse``
        array" — also wrong, and refuted by the re-run command printed directly beneath it, which
        returns ``None`` (key absent), not ``[]``. Both errors are the same error: a claim written
        next to the command that would have checked it.
        """
        education = self._education()
        for project in (
            "agentic_journal",
            "VerificationPortal",
            "howie_family_wiki",
            "dan_research_karpathy_wiki",
        ):
            assert project in education, f"{project} also carries the bypass and must be named"
        assert "five checkouts, not one file" in education
        assert "no `PreToolUse` key at all" in education, (
            "the worst of the four must be called out, in the state it is actually in"
        )
        assert "PreToolUse` array is empty" not in education, (
            "the disproved 'empty array' wording must not survive alongside the correction"
        )

    def test_the_row_discloses_the_inline_python_false_positive_class(self) -> None:
        """Finding: the measured false-positive class was disclosed NOWHERE.

        ``deny`` has no in-session override, so an undisclosed false-positive class is a trap for
        whoever hits it. The row must name the class, show the shapes, and say it is fixed — and
        the code's docstring must agree (asserted in the inline-python test class).
        """
        education = self._education()
        assert "whether the write was aimed at the protected path" in education
        assert "shutil.copy('metrics/evaluation.db','/tmp/scratch.db')" in education
        assert "sys.stdout.write" in education, "the print-to-screen shape must be shown"
        assert "exactly one step and no further" in education, "the one-hop limit must be stated"

    def test_the_row_does_not_claim_a_corpus_size_it_could_not_reproduce(self) -> None:
        """The third-round re-measurement must report what did NOT reproduce, not only what did.

        Re-running the corpus from this row's own description reproduced ``denies 0 / asks 2`` and
        the file counts, but not the block/line counts — the slicing is under-specified. This file
        already carries a paragraph retiring an earlier unreproducible corpus; the fix for that
        class is to say so, not to quietly restate a number.
        """
        education = self._education()
        assert "did not reproduce the corpus counts" in education
        assert "denies 0, asks 2" in education

    def test_the_template_line_count_in_the_table_is_current(self) -> None:
        """A number in prose rots silently; this makes it rot LOUDLY.

        The checkout table's own line count for this validator was stale by 263 lines when this
        round started, and went stale again *twice* while that was being corrected — once inside
        the very edit that corrected it. Care is not the remedy for that; a check is. This is the
        same discipline the module docstring already applies to ADR line citations ("cited by
        content, not by line number, on purpose").
        """
        row = self._table_row_containing("this template")
        claimed = re.search(r"([\d,]+) lines", row)
        assert claimed is not None, f"no line count in the template row: {row!r}"
        actual = len(HOOK_PATH.read_text(encoding="utf-8").splitlines())
        assert int(claimed.group(1).replace(",", "")) == actual, (
            f"the education table says {claimed.group(1)} lines; the file is {actual}. "
            "Update the row in the same commit as the code."
        )

    @staticmethod
    def _table_row_containing(needle: str) -> str:
        path = REPO_ROOT / "docs" / "education" / "governance-mechanisms.md"
        rows = [
            line
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip().startswith("|") and needle in line
        ]
        assert len(rows) == 1, f"expected exactly one row containing {needle!r}, found {len(rows)}"
        return rows[0]


# ---------------------------------------------------------------------------
# Wiring status — the guard is inert until settings.json is updated
# ---------------------------------------------------------------------------


class TestWiringStatus:
    def test_documents_whether_each_shell_tool_is_wired(self) -> None:
        """The guard is dead code until .claude/settings.json runs it on a shell matcher.

        This test does not fail on the un-wired state (the developer applies that edit by hand;
        settings.json is protected). It asserts the states are distinguishable, so nobody can
        read a green suite as proof the guard is live.

        BOTH shell tools are checked. Wiring only ``Bash`` would leave the ``PowerShell`` tool
        unrouted — and PowerShell is this repo's declared primary shell, so a Bash-only matcher
        is the smaller half of the fix, not the fix.
        """
        settings = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text())
        entries = settings.get("hooks", {}).get("PreToolUse", [])

        def wired_for(tool: str) -> bool:
            return any(
                "pre-tool-use-validator" in h.get("command", "")
                for entry in entries
                if tool in entry.get("matcher", "")
                for h in entry.get("hooks", [])
            )

        unwired = [tool for tool in ("Bash", "PowerShell") if not wired_for(tool)]
        assert all(isinstance(wired_for(t), bool) for t in ("Bash", "PowerShell"))
        if unwired:
            pytest.skip(
                f"pre-tool-use-validator.sh is not wired for {', '.join(unwired)} — the command "
                "guard is INERT for those tools in this checkout. Apply the settings.json "
                'snippet from the slice report ("matcher": "Bash|PowerShell").'
            )


# ---------------------------------------------------------------------------
# Round 4: the parser skipped past the real command word
# ---------------------------------------------------------------------------

_D = "discussions/2026-08-07"
_EV = "discussions/2026-08-07/DISC-1/events.jsonl"


@pytest.mark.regression
class TestGroupingAndControlFlowDoNotHideTheCommand:
    """Every one of these returned ALLOW before the fix, path spelled out in full.

    The cause was one line: ``_parse_segment`` took the first non-flag token of a segment as the
    command, so a leading ``do`` / ``then`` / ``try`` / ``(`` / ``ForEach-Object`` shadowed the
    real verb. Nothing was obfuscated and no verb was missing from the tables — the parser simply
    never reached them.
    """

    @pytest.mark.parametrize(
        "command",
        [
            f"( rm -rf {_D} )",
            f"(rm -rf {_D})",
            f"{{ rm -rf {_D}; }}",
            f"for f in 1; do rm -rf {_D}; done",
            f"while true; do rm -rf {_D}; done",
            f"until false; do rm -rf {_D}; done",
            f"if true; then rm -rf {_D}; fi",
            f"1 | ForEach-Object {{ Remove-Item -Recurse -Force {_D} }}",
            f"foreach ($i in 1) {{ Remove-Item -Recurse -Force {_D} }}",
            f"try {{ Remove-Item -Recurse -Force {_D} }} catch {{ }}",
            f"1 | % {{ Clear-Content {_EV} }}",
            f"if ($true) {{ Clear-Content {_EV} }}",
            f"if (Test-Path {_D}) {{ Remove-Item -Recurse -Force {_D} }}",
        ],
    )
    def test_wrapped_destruction_is_denied(self, command: str) -> None:
        assert _decision(command) == "deny", (
            f"grouping/control flow still hides the verb: {command}"
        )

    def test_a_leading_subshell_still_resolves_cd_for_later_relative_paths(self) -> None:
        """The keyword-header skip must NOT swallow a subshell's own first command.

        ``(cd discussions && rm -rf 2026-08-07)`` only resolves because the guard reads that
        ``cd``. Skipping every ``(`` — rather than only a ``(`` that FOLLOWS a keyword — would
        have silently broken this.
        """
        assert _decision("(cd discussions && rm -rf 2026-08-07)") == "deny"

    def test_ordinary_loops_over_unprotected_paths_still_run(self) -> None:
        """The fix can only ADD detections, so the false-positive check is the one that matters."""
        for command in (
            "for f in 1; do rm -rf build/tmp; done",
            "for f in *.py; do ruff format $f; done",
            "if true; then python -m pytest; fi",
            "1 | ForEach-Object { Write-Output $_ }",
            "try { python -m pytest } catch { }",
        ):
            assert _decision(command) is None, f"false positive on ordinary work: {command}"

    def test_lead_words_do_not_shadow_a_real_destructive_verb(self) -> None:
        """The reserved-word set must be disjoint from every verb table.

        This is the claim that makes skipping safe. A word in both sets would be skipped as a
        keyword and never matched as a verb — silently removing coverage.
        """
        verbs = (
            hook.DESTRUCTIVE_ALL_ARGS
            | hook.DESTRUCTIVE_DEST_ONLY
            | hook.DESTROY_VERBS
            | hook.DESTRUCTIVE_GIT_SUBCOMMANDS
        )
        overlap = hook.NON_COMMAND_LEAD_WORDS & verbs
        assert not overlap, f"reserved words shadow real destructive verbs: {sorted(overlap)}"


@pytest.mark.regression
class TestCombinedShortFlagsAreUnwrapped:
    """``bash -lc '<payload>'`` fused ``-c`` into a flag cluster and skipped unwrapping."""

    @pytest.mark.parametrize("flags", ["-lc", "-ec", "-euxc", "-c"])
    def test_posix_payload_is_unwrapped(self, flags: str) -> None:
        assert _decision(f"bash {flags} 'rm -rf {_D}'") == "deny"

    def test_long_options_are_not_mistaken_for_the_payload_flag(self) -> None:
        """``--norc`` also ends in ``c``; matching it would capture the wrong payload."""
        assert _decision(f"bash --norc -c 'rm -rf {_D}'") == "deny"
        assert _decision(f"bash --noprofile --norc -c 'rm -rf {_D}'") == "deny"

    def test_running_a_script_file_is_still_not_a_payload(self) -> None:
        """``bash cleanup.sh`` stays in the CANNOT list — it must not falsely match."""
        assert _decision("bash cleanup.sh") is None


@pytest.mark.regression
class TestSecondArgumentDestinationVerbs:
    """``robocopy SOURCE DEST [files]`` names its destination second, not last."""

    def test_robocopy_destination_is_the_second_operand(self) -> None:
        assert _decision(f"robocopy C:/tmp {_D} *.jsonl") == "deny"

    def test_xcopy_destination_is_the_second_operand(self) -> None:
        assert _decision(f"xcopy C:/tmp/x {_D}") == "deny"

    def test_copying_between_unprotected_paths_still_runs(self) -> None:
        assert _decision("robocopy C:/tmp C:/tmp2 *.jsonl") is None

    def test_a_normal_dest_only_verb_still_uses_its_last_operand(self) -> None:
        assert _decision(f"cp /tmp/x {_EV}") == "deny"
        assert _decision("cp metrics/evaluation.db /tmp/backup.db") is None


class TestScopeIsDisclosedNotOverclaimed:
    """The round-4 retraction: defence-in-depth, not a boundary.

    Three rounds each closed a bypass and each claimed the class. These pins exist so the claim
    cannot quietly re-inflate — which is the specific defect this whole effort is removing.
    """

    def test_the_code_calls_itself_defence_in_depth_and_not_a_boundary(self) -> None:
        source = HOOK_PATH.read_text(encoding="utf-8")
        assert "It is NOT a\n  boundary" in source or "is NOT a boundary" in source.replace(
            "\n  ", " "
        ), "the docstring must retract the boundary claim"
        assert "unwinnable" in source, "the docstring must name why it stopped enumerating"

    def test_the_code_points_at_the_deterministic_control(self) -> None:
        source = HOOK_PATH.read_text(encoding="utf-8")
        assert "scripts/verify_layer1_integrity.py" in source
        assert "check_layer1_integrity" in source

    def test_the_code_discloses_what_it_declined_to_fix(self) -> None:
        """Leaving a gap open is only honest if the gap is written down."""
        source = HOOK_PATH.read_text(encoding="utf-8")
        assert "KNOWN-OPEN AND DELIBERATELY NOT FIXED" in source
        for shape in ("perl -i", "attrib -r", "Path.replace"):
            assert shape in source, f"undisclosed known gap: {shape}"

    def test_the_education_row_retracts_the_boundary_claim(self) -> None:
        education = (REPO_ROOT / "docs" / "education" / "governance-mechanisms.md").read_text(
            encoding="utf-8"
        )
        assert "not* a\n> boundary" in education or "not a boundary" in education.replace(
            "\n> ", " "
        ).replace("*", ""), "the education row must retract the boundary claim"

    def test_the_explain_back_no_longer_claims_deny_covers_the_irreversible(self) -> None:
        """The measured overclaim: an ordinary loop was allowed while the row said otherwise."""
        education = (REPO_ROOT / "docs" / "education" / "governance-mechanisms.md").read_text(
            encoding="utf-8"
        )
        # Bound the slice at the sentence's own closing ``"*`` rather than by a character count.
        # A fixed window ran past the end into the note BELOW it, which legitimately quotes the
        # old claim in order to explain why it was wrong — the identical false-fire already
        # recorded in TestEducationRowMatchesTheCode. The row the reader explains back is the
        # thing under test, so the row is what must be sliced.
        start = education.index("**One-sentence explain-back you should be able to give:**")
        sentence = education[start : education.index('"*', start) + 2]
        # Markdown wraps and emphasis markers must not decide whether a claim is present.
        flat = " ".join(sentence.replace("*", "").split())
        assert "deny the irreversible things" not in sentence
        assert "defence-in-depth, not a boundary" in flat
        # And the note below it must still preserve the retracted claim as history.
        assert "deny the irreversible things" in education

    def test_the_education_row_names_the_grouping_bypass_it_closed(self) -> None:
        education = (REPO_ROOT / "docs" / "education" / "governance-mechanisms.md").read_text(
            encoding="utf-8"
        )
        assert "do rm -rf discussions" in education
        assert "ForEach-Object" in education
        assert "bash -lc" in education

    def test_the_education_file_documents_the_detective_control(self) -> None:
        education = (REPO_ROOT / "docs" / "education" / "governance-mechanisms.md").read_text(
            encoding="utf-8"
        )
        assert "Row 2 — Layer 1 sealed-record integrity check" in education
        assert "verify_layer1_integrity.py" in education
        assert "CHANGED SINCE SEALING" in education
        assert "UNKNOWN" in education
        assert "SUSPECT" in education
        assert "Detection is not prevention" in education
