"""External supervisor for autonomous multi-session continuation (ADR-0018 v2).

Chains fresh ``claude -p`` (headless) sessions via a rolling handoff file, so a
long task survives context limits by rolling to a NEW full-context session
instead of either lossy auto-compaction or manual paste. This is the robust
replacement for ADR-0018's original in-session ``subprocess.Popen`` self-spawn,
which wedged: a headless run with NO permission flag hangs forever on the first
tool-permission request (verified 2026-06-07, CLI v2.1.143). The fix, also
verified, is ``--permission-mode bypassPermissions``.

Why a supervisor (not self-spawn): a dying session cannot reliably spawn its own
successor. The supervisor is a plain process with NO LLM context of its own, so
it never fills up; it owns the lifecycle and re-spawns fresh sessions. Real exit
codes + JSON output + the progress log make "did the run make progress?" a fact,
not an inference.

Per-session contract: each spawned session reads the rolling handoff, does work,
updates the handoff IN PLACE, and ends its final message with exactly one
sentinel line:
  * ``SUPERVISOR_DONE`` — the whole task is complete (supervisor stops), or
  * ``SUPERVISOR_ROLL`` — roll to a fresh session (supervisor relaunches).
A run that ends with neither sentinel STOPS the loop (no blind relaunch), so a
confused session can never spin forever.

Safety: sessions run with ``--permission-mode bypassPermissions`` (so tools do
not hang on approval) but WITHOUT ``--bare`` — so the project's PreToolUse hooks
still fire: the pre-push blocker, the settings.json validator, and the
pre-commit quality gate still enforce "no push / no settings edit /
review-before-commit" deterministically. bypassPermissions DOES allow arbitrary
local Bash, so run this ONLY on a feature branch you trust, bounded by the
``--max-sessions``, ``--max-budget-usd``, and ``--per-session-timeout`` caps.

stdlib-only. CLI::

    python scripts/session_supervisor.py --handoff docs/handoff/HANDOFF-...md \
        [--max-sessions 6] [--max-budget-usd 8] [--per-session-timeout 2400] \
        [--max-turns 80] [--progress-log docs/handoff/.supervisor-progress.md] \
        [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

SENTINEL_DONE = "SUPERVISOR_DONE"
SENTINEL_ROLL = "SUPERVISOR_ROLL"

DEFAULT_MAX_SESSIONS = 6
DEFAULT_PER_SESSION_TIMEOUT = 2400  # seconds (40 min)
DEFAULT_MAX_TURNS = 80
DEFAULT_PROGRESS_LOG = "docs/handoff/.supervisor-progress.md"

# (returncode, stdout, stderr)
RunResult = tuple[int, str, str]
Runner = Callable[[list[str], Path, int], RunResult]


def build_prompt(handoff_path: Path) -> str:
    """Build the per-session prompt seeding the rolling handoff (pure).

    Only the validated, absolute handoff path is interpolated — no untrusted
    text — and the command runs with ``shell=False``, so this is injection-safe.
    A defensive guard rejects control characters in the path (a path containing
    a newline + a sentinel string could otherwise spoof DONE/ROLL).
    """
    if any(c in str(handoff_path) for c in "\n\r\x00"):
        raise ValueError("handoff path contains control characters")
    return (
        f"Read the session handoff at {handoff_path} and continue the work it "
        "describes. You inherit the full CLAUDE.md and rules: run /review before "
        "any commit, never bypass capture, never push or auto-merge, and stop on "
        "genuine design forks. As your context approaches its wrap-up threshold, "
        "or when you finish a self-contained unit of work, UPDATE the handoff "
        f"file at {handoff_path} IN PLACE with the current state + exact next "
        "steps, then end your final message with exactly one line: "
        f"'{SENTINEL_DONE}' if the entire task is complete, otherwise "
        f"'{SENTINEL_ROLL}' to continue in a fresh full-context session."
    )


def build_command(
    prompt: str,
    *,
    permission_mode: str = "bypassPermissions",
    output_format: str = "json",
    max_turns: int | None = DEFAULT_MAX_TURNS,
    max_budget_usd: float | None = None,
) -> list[str]:
    """Build the headless ``claude -p`` argv (pure).

    NOTE: deliberately omits ``--bare`` — that flag forces ANTHROPIC_API_KEY-only
    auth (breaking an OAuth subscription) AND skips the project's safety hooks.
    The prompt is a discrete argv element; run with ``shell=False``.
    """
    cmd = [
        "claude",
        "-p",
        prompt,
        "--permission-mode",
        permission_mode,
        "--output-format",
        output_format,
    ]
    if max_turns is not None:
        cmd += ["--max-turns", str(max_turns)]
    if max_budget_usd is not None:
        cmd += ["--max-budget-usd", str(max_budget_usd)]
    return cmd


def parse_result(stdout: str) -> dict | None:
    """Parse the ``--output-format json`` result object, or None (pure, no I/O).

    The json format prints a single result object. Be tolerant of leading log
    lines: scan lines from the bottom for the last parseable JSON object that
    carries a ``result`` or ``subtype`` field.
    """
    lines = [ln for ln in stdout.splitlines() if ln.strip()]
    for line in reversed(lines):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and ("result" in obj or "subtype" in obj):
            return obj
    return None


def result_tokens(parsed: dict) -> int:
    """Total input+output tokens for a run (pure); 0 if absent."""
    usage = parsed.get("usage") or {}
    return int(usage.get("input_tokens", 0) or 0) + int(usage.get("output_tokens", 0) or 0)


def classify_result(parsed: dict | None) -> str:
    """Classify a parsed run result (pure).

    Returns one of: ``"done"`` (task complete sentinel), ``"roll"`` (relaunch
    sentinel), ``"error"`` (run errored / missing), ``"unknown"`` (no sentinel —
    the supervisor stops rather than blindly relaunch). DONE wins over ROLL if
    both appear (a completed task should not be relaunched).
    """
    if parsed is None or parsed.get("is_error"):
        return "error"
    text = str(parsed.get("result") or "")
    if SENTINEL_DONE in text:
        return "done"
    if SENTINEL_ROLL in text:
        return "roll"
    return "unknown"


def _default_runner(cmd: list[str], cwd: Path, timeout: int) -> RunResult:
    """Run one headless session via subprocess (the only I/O seam).

    Resolves ``cmd[0]`` via ``shutil.which`` first: on Windows ``claude`` is a
    ``claude.CMD`` npm shim, and bare ``subprocess.run(["claude", ...],
    shell=False)`` raises ``FileNotFoundError`` because ``CreateProcess`` does not
    apply ``PATHEXT``. The resolved absolute path runs correctly with shell=False
    (no injection surface added).
    """
    exe = shutil.which(cmd[0]) or cmd[0]
    resolved = [exe, *cmd[1:]]
    try:
        proc = subprocess.run(
            resolved,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return (124, "", f"session timed out after {timeout}s")
    return (proc.returncode, proc.stdout or "", proc.stderr or "")


def _is_clean_tree(cwd: Path) -> bool:
    """True if the git working tree has no uncommitted changes.

    Returns True (proceed) when git is unavailable or ``cwd`` is not a repo —
    there is nothing to protect then. Only a confirmed-dirty repo returns False.
    This backs the clean-tree preflight that makes a ``bypassPermissions`` run
    recoverable: if a spawned session destroys the working tree, committed state
    survives and ``git checkout -- .`` restores the rest.
    """
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return True
    if proc.returncode != 0:
        return True
    return proc.stdout.strip() == ""


def _append_progress(log_path: Path, line: str) -> None:
    """Append one timestamped line to the progress log (best-effort).

    The progress log is the operator's monitorability trail (the developer
    explicitly asked for ongoing evidence the chain is working), so a write
    failure is surfaced on stderr rather than swallowed silently.
    """
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"- {stamp} {line}\n")
    except OSError as exc:
        sys.stderr.write(f"WARN: progress log unwritable ({type(exc).__name__}): {log_path}\n")


def supervise(
    handoff_path: Path,
    *,
    max_sessions: int = DEFAULT_MAX_SESSIONS,
    max_budget_usd: float | None = None,
    per_session_timeout: int = DEFAULT_PER_SESSION_TIMEOUT,
    max_turns: int | None = DEFAULT_MAX_TURNS,
    progress_log: Path | None = None,
    cwd: Path | None = None,
    runner: Runner = _default_runner,
    dry_run: bool = False,
    allow_dirty: bool = False,
    tree_checker: Callable[[Path], bool] = _is_clean_tree,
) -> dict:
    """Chain fresh sessions until DONE, a cap is hit, or a run stops the loop.

    Returns a summary dict: ``{"sessions": N, "outcome": str, "cost_usd": float}``.
    ``outcome`` is one of done / max-sessions / budget / error / unknown-stop /
    handoff-missing / dirty-tree / dry-run.

    Safety preflight: unless ``allow_dirty`` is set, a dirty git working tree
    aborts the run (``dirty-tree``) so a ``bypassPermissions`` session can't
    destroy uncommitted work irrecoverably.
    """
    cwd = cwd or Path.cwd()
    log = progress_log or (cwd / DEFAULT_PROGRESS_LOG)
    if not handoff_path.exists():
        _append_progress(log, f"ABORT: handoff not found: {handoff_path}")
        return {"sessions": 0, "outcome": "handoff-missing", "cost_usd": 0.0}
    if not dry_run and not allow_dirty and not tree_checker(cwd):
        _append_progress(log, "ABORT: working tree dirty (commit/stash, or pass --allow-dirty)")
        return {"sessions": 0, "outcome": "dirty-tree", "cost_usd": 0.0}

    spent = 0.0
    for i in range(1, max_sessions + 1):
        prompt = build_prompt(handoff_path.resolve())
        cmd = build_command(
            prompt,
            max_turns=max_turns,
            max_budget_usd=max_budget_usd,
        )
        if dry_run:
            _append_progress(log, f"DRY-RUN session {i}: {' '.join(cmd[:6])} ...")
            return {"sessions": 0, "outcome": "dry-run", "cost_usd": 0.0}

        _append_progress(log, f"session {i}/{max_sessions} START")
        rc, out, err = runner(cmd, cwd, per_session_timeout)
        parsed = parse_result(out)
        action = classify_result(parsed)
        cost = float(parsed.get("total_cost_usd", 0.0)) if parsed else 0.0
        spent += cost
        toks = result_tokens(parsed) if parsed else 0
        snippet = str(parsed.get("result"))[:120] if parsed else (err[:120] or "no output")
        _append_progress(
            log,
            f"session {i} END rc={rc} action={action} cost=${cost:.4f} "
            f"tokens={toks} cumcost=${spent:.4f} :: {snippet}",
        )

        if action == "error" or rc != 0:
            return {"sessions": i, "outcome": "error", "cost_usd": spent}
        if action == "done":
            _append_progress(log, f"DONE after {i} session(s), ${spent:.4f}")
            return {"sessions": i, "outcome": "done", "cost_usd": spent}
        if action == "unknown":
            _append_progress(log, f"STOP: session {i} ended with no sentinel")
            return {"sessions": i, "outcome": "unknown-stop", "cost_usd": spent}
        if max_budget_usd is not None and spent >= max_budget_usd:
            _append_progress(log, f"STOP: budget ${spent:.4f} >= ${max_budget_usd}")
            return {"sessions": i, "outcome": "budget", "cost_usd": spent}
        # action == "roll" and under caps -> loop (handoff updated in place)

    _append_progress(log, f"STOP: reached max-sessions={max_sessions}, ${spent:.4f}")
    return {"sessions": max_sessions, "outcome": "max-sessions", "cost_usd": spent}


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    p = argparse.ArgumentParser(description="Autonomous multi-session supervisor (ADR-0018 v2).")
    p.add_argument("--handoff", required=True, help="Path to the rolling handoff file.")
    p.add_argument("--max-sessions", type=int, default=DEFAULT_MAX_SESSIONS)
    p.add_argument("--max-budget-usd", type=float, default=None)
    p.add_argument("--per-session-timeout", type=int, default=DEFAULT_PER_SESSION_TIMEOUT)
    p.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS)
    p.add_argument("--progress-log", default=DEFAULT_PROGRESS_LOG)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Skip the clean-git-tree preflight (uncommitted work is then at risk).",
    )
    args = p.parse_args(argv)

    summary = supervise(
        Path(args.handoff),
        max_sessions=args.max_sessions,
        max_budget_usd=args.max_budget_usd,
        per_session_timeout=args.per_session_timeout,
        max_turns=args.max_turns,
        progress_log=Path(args.progress_log),
        dry_run=args.dry_run,
        allow_dirty=args.allow_dirty,
    )
    print(json.dumps(summary))
    return 0 if summary["outcome"] in ("done", "dry-run") else 1


if __name__ == "__main__":
    raise SystemExit(main())
