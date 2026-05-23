"""Safety preflight for ``/distribute`` — the opt-in HARD GATE and skip-if-busy check.

A target is only eligible to receive a staged framework update when **both** hold:

1. **Opt-in** — the target declares ``custodian.accepts_distribution: true`` in its own
   ``framework-lineage.yaml`` (per-instance assent; same absolute shape as a pinned trait).
2. **Safe** — its git working tree is clean, HEAD is on a branch (not detached), no merge /
   rebase / cherry-pick / revert / bisect is in progress, and a lineage manifest exists.

A target failing either condition is **skipped on the write path** — recorded and reported,
never written to. ``--dry-run`` callers still compute the report and surface the predicted
``SKIPPED`` route; the gate only blocks the actual ``stage_branch`` write.

The optional baseline quality-gate check (:func:`baseline_gate_green`) is kept separate so
the cheap git/manifest preflight stays fast and unit-testable; the orchestrator runs the
gate only on the live (non-dry-run) path.

Usage:
    python scripts/distribute/repo_safety_check.py /path/to/target
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Ensure project root is on sys.path for both CLI and module usage.
_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.distribute._git_utils import git_cmd as _git  # noqa: E402
from scripts.lineage.manifest import manifest_read  # noqa: E402

MANIFEST_NAME = "framework-lineage.yaml"

# git-dir marker files/dirs indicating an in-progress operation that staging must not disturb.
_IN_PROGRESS_MARKERS: dict[str, str] = {
    "rebase-merge": "rebase in progress",
    "rebase-apply": "rebase in progress",
    "MERGE_HEAD": "merge in progress",
    "CHERRY_PICK_HEAD": "cherry-pick in progress",
    "REVERT_HEAD": "revert in progress",
    "BISECT_LOG": "bisect in progress",
}


@dataclass
class SafetyReport:
    """Result of the distribution safety preflight for a single target.

    Attributes:
        target_path: Absolute path of the target repository.
        opted_in: True if the target declares ``custodian.accepts_distribution: true``.
        is_safe: True if no git-state or manifest blockers were found.
        blockers: Human-readable reasons the target is unsafe (empty when safe).
        accept_paths: Optional per-path allow-list globs from ``custodian.accept_paths``.
        deny_paths: Optional per-path deny-list globs from ``custodian.deny_paths``.
        branch: The checked-out branch name, or None if detached / undetermined.
    """

    target_path: str
    opted_in: bool
    is_safe: bool
    blockers: list[str] = field(default_factory=list)
    accept_paths: list[str] = field(default_factory=list)
    deny_paths: list[str] = field(default_factory=list)
    branch: str | None = None

    @property
    def can_proceed(self) -> bool:
        """True only when the target is both opted-in and safe (the write-path gate)."""
        return self.opted_in and self.is_safe

    @property
    def skip_reason(self) -> str | None:
        """Categorise why a target would be skipped, or None if it can proceed.

        Returns:
            ``"not-opted-in"``, ``"unsafe"``, or None.
        """
        if not self.opted_in:
            return "not-opted-in"
        if not self.is_safe:
            return "unsafe"
        return None


def _in_progress_operation(target_path: Path) -> str | None:
    """Detect an in-progress git operation that staging must not disturb.

    Args:
        target_path: Repository working directory.

    Returns:
        A description of the in-progress operation, or None if the repo is idle.
        Fails closed: if the git-dir cannot be resolved, returns a blocker string
        rather than None so an unverifiable state is never treated as idle.
    """
    result = _git(target_path, "rev-parse", "--git-dir")
    if result.returncode != 0:
        return "git-dir lookup failed — cannot verify in-progress state"
    git_dir = Path(result.stdout.strip())
    if not git_dir.is_absolute():
        git_dir = (target_path / git_dir).resolve()
    for marker, description in _IN_PROGRESS_MARKERS.items():
        if (git_dir / marker).exists():
            return description
    return None


def _check_git_state(target_path: Path) -> tuple[list[str], str | None]:
    """Inspect git state for conditions that make staging unsafe.

    Args:
        target_path: Repository working directory.

    Returns:
        A tuple of (blockers, branch_name). ``branch_name`` is None when detached
        or when the repo cannot be inspected.
    """
    blockers: list[str] = []

    if shutil.which("git") is None:
        return ["git executable not found on PATH"], None

    inside = _git(target_path, "rev-parse", "--is-inside-work-tree")
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return ["not a git working tree"], None

    branch: str | None = None
    head = _git(target_path, "symbolic-ref", "-q", "--short", "HEAD")
    if head.returncode != 0 or not head.stdout.strip():
        blockers.append("HEAD is detached (not on a branch)")
    else:
        branch = head.stdout.strip()

    status = _git(target_path, "status", "--porcelain")
    if status.stdout.strip():
        blockers.append("working tree is dirty (uncommitted or untracked changes)")

    in_progress = _in_progress_operation(target_path)
    if in_progress:
        blockers.append(in_progress)

    return blockers, branch


def repo_safety_check(target_path: Path | str) -> SafetyReport:
    """Run the distribution safety preflight for one target repository.

    Performs cheap, read-only checks: opt-in declaration, lineage-manifest presence, and
    git working-tree state. Does NOT run the baseline quality gate — call
    :func:`baseline_gate_green` separately on the live path.

    Args:
        target_path: Path to the target repository root.

    Returns:
        A :class:`SafetyReport`. Inspect ``can_proceed`` for the write-path decision.
    """
    target = Path(target_path).resolve()
    blockers: list[str] = []

    if not target.is_dir():
        return SafetyReport(
            target_path=str(target),
            opted_in=False,
            is_safe=False,
            blockers=[f"target path is not a directory: {target}"],
        )

    # Opt-in HARD GATE + per-path globs from the target's own manifest.
    opted_in = False
    accept_paths: list[str] = []
    deny_paths: list[str] = []
    manifest_path = target / MANIFEST_NAME
    try:
        manifest = manifest_read(manifest_path)
    except FileNotFoundError:
        blockers.append(f"no lineage manifest ({MANIFEST_NAME}) — target is not framework-tracked")
        manifest = None
    except (ValueError, OSError, yaml.YAMLError) as exc:
        blockers.append(f"lineage manifest unreadable: {exc}")
        manifest = None

    if manifest is not None:
        custodian = manifest.get("custodian") or {}
        if isinstance(custodian, dict):
            opted_in = custodian.get("accepts_distribution") is True
            accept_paths = list(custodian.get("accept_paths") or [])
            deny_paths = list(custodian.get("deny_paths") or [])

    git_blockers, branch = _check_git_state(target)
    blockers.extend(git_blockers)

    return SafetyReport(
        target_path=str(target),
        opted_in=opted_in,
        is_safe=len(blockers) == 0,
        blockers=blockers,
        accept_paths=accept_paths,
        deny_paths=deny_paths,
        branch=branch,
    )


def baseline_gate_green(
    target_path: Path | str,
    *,
    timeout: int = 600,
) -> tuple[bool, str]:
    """Run the target's own quality gate to establish a pre-stage baseline.

    Runs ``python scripts/quality_gate.py`` with the target as the working directory, so the
    target's own thresholds and rules apply. Kept separate from :func:`repo_safety_check`
    because it is slow (runs the test suite) and is only needed on the live write path.

    SECURITY — code-execution surface: this runs the *target's* ``scripts/quality_gate.py``,
    a file the target repository controls. An opted-in but adversarial target could ship a
    modified gate script that executes arbitrary code on the distributor machine under the
    operator's user. This is acceptable only when distributor and targets are single-owner
    (the framework's intended use). The orchestrator MUST surface this before calling on the
    live path; never call this against a target you would not trust to run code locally.

    Args:
        target_path: Path to the target repository root.
        timeout: Maximum seconds to allow the gate to run.

    Returns:
        A tuple of (is_green, summary). ``summary`` is the trailing output for diagnostics.
    """
    target = Path(target_path).resolve()
    gate_script = target / "scripts" / "quality_gate.py"
    try:
        if not gate_script.is_file():
            return False, f"no quality_gate.py at {gate_script}"
    except OSError as exc:
        return False, f"cannot stat quality gate script: {exc}"
    try:
        result = subprocess.run(
            [sys.executable, "scripts/quality_gate.py"],
            cwd=str(target),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"quality gate timed out after {timeout}s"
    tail = (result.stdout or "")[-1500:]
    return result.returncode == 0, tail


def main() -> None:
    """CLI entry point — print a safety report for a target path."""
    parser = argparse.ArgumentParser(description="Distribution safety preflight for a target repo")
    parser.add_argument("target", help="Path to the target repository root")
    parser.add_argument(
        "--baseline-gate",
        action="store_true",
        help="Also run the target's quality gate (slow; live-path baseline)",
    )
    args = parser.parse_args()

    report = repo_safety_check(args.target)
    print(f"Target:    {report.target_path}")
    print(f"Opted in:  {report.opted_in}")
    print(f"Branch:    {report.branch or '(detached/unknown)'}")
    print(f"Safe:      {report.is_safe}")
    print(f"Proceed:   {report.can_proceed}  (skip_reason={report.skip_reason})")
    if report.accept_paths:
        print(f"accept_paths: {report.accept_paths}")
    if report.deny_paths:
        print(f"deny_paths:   {report.deny_paths}")
    if report.blockers:
        print("Blockers:")
        for blocker in report.blockers:
            print(f"  - {blocker}")

    if args.baseline_gate:
        green, summary = baseline_gate_green(args.target)
        print(f"Baseline gate green: {green}")
        if not green:
            print(summary)


if __name__ == "__main__":
    main()
