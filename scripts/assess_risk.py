"""Score a change from its diff and choose how deeply it should be taught.

The education gate exists so the developer can make the *next* decision well.
That means the depth of a briefing should track how much a wrong next decision
would cost — which is a property of the diff, not of how the session feels.

Scoring is deterministic and lives here rather than in a prompt so that the
depth cannot drift with model mood, session length, or how eager anyone is to
ship. Signals are additive and each carries a plain-language reason, because a
briefing that cannot explain why it fired teaches nothing.

    light     (0-1)  a change you can absorb from three lines
    standard  (2-4)  a change with a live tradeoff you should hold
    deep      (5+)   a change you will regret not understanding

Usage:
    python scripts/assess_risk.py                 # working tree vs HEAD
    python scripts/assess_risk.py --staged        # staged changes only
    python scripts/assess_risk.py --base main     # branch vs merge-base
    python scripts/assess_risk.py --json          # machine-readable
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

LIGHT_MAX = 1
STANDARD_MAX = 4

SECURITY_PATH = re.compile(
    r"(auth|login|session|crypto|secret|token|password|permission|credential|sanitiz|escape)",
    re.IGNORECASE,
)
SCHEMA_PATH = re.compile(r"(migration|schema|models?\.py|init_db)", re.IGNORECASE)
DEPENDENCY_PATH = re.compile(
    r"(pyproject\.toml|requirements.*\.txt|package(-lock)?\.json|Cargo\.(toml|lock)|go\.(mod|sum))"
)
TEST_PATH = re.compile(r"(^|/)tests?/|(^|/)test_[^/]*\.py$|_test\.py$")
SOURCE_EXT = re.compile(r"\.(py|ts|tsx|js|jsx|go|rs|java|rb|sh)$")
# Prose that merely discusses auth is not auth. Without this, a skill document
# mentioning "session" scores the same as touching the session store.
DOC_EXT = re.compile(r"\.(md|markdown|rst|txt)$", re.IGNORECASE)


@dataclass
class Signal:
    """One reason a change scored the way it did."""

    weight: int
    reason: str


@dataclass
class RiskAssessment:
    """The computed depth for a change, with the reasons behind it."""

    score: int
    depth: str
    files_changed: int
    lines_added: int
    lines_removed: int
    signals: list[Signal] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Render the assessment as a JSON-serializable dict."""
        return {
            "score": self.score,
            "depth": self.depth,
            "files_changed": self.files_changed,
            "lines_added": self.lines_added,
            "lines_removed": self.lines_removed,
            "signals": [{"weight": s.weight, "reason": s.reason} for s in self.signals],
        }


def depth_for_score(score: int) -> str:
    """Map a numeric score to a briefing depth."""
    if score <= LIGHT_MAX:
        return "light"
    if score <= STANDARD_MAX:
        return "standard"
    return "deep"


class GitUnavailable(RuntimeError):
    """A git command failed, so no assessment could be made.

    This is deliberately not swallowed. Returning an empty diff on failure
    would score 0 and print LIGHT, making "assessment did not run"
    indistinguishable from "assessed, low risk" — and failing toward *less*
    teaching, which is the one direction this tool must never fail in.
    """


def _run_git(args: list[str], cwd: Path) -> str:
    """Run a git command and return stdout.

    Raises:
        GitUnavailable: if git is missing, times out, or exits non-zero.
    """
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GitUnavailable(f"git {' '.join(args)} could not run: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip().splitlines()
        raise GitUnavailable(
            f"git {' '.join(args)} failed: {detail[0] if detail else 'unknown error'}"
        )
    return result.stdout


def _diff_range(base: str | None, staged: bool, cwd: Path) -> list[str]:
    """Build the git diff range arguments for the selected mode.

    With no base and no --staged the range is ``HEAD``, not the empty range.
    A bare ``git diff`` compares the working tree against the *index*, so once
    work is staged it reports nothing — which silently under-teaches at exactly
    the moment someone is about to commit.
    """
    if base:
        try:
            merge_base = _run_git(["merge-base", base, "HEAD"], cwd).strip()
        except GitUnavailable:
            merge_base = ""
        return [merge_base or base, "HEAD"]
    if staged:
        return ["--cached"]
    return ["HEAD"]


def collect_diff(
    base: str | None = None, staged: bool = False, cwd: Path = PROJECT_ROOT
) -> tuple[list[str], list[str], list[str]]:
    """Return (changed paths, numstat lines, added paths) for the selected range.

    Added paths come from the same range as the diff via ``--diff-filter=A``,
    so they describe the change being assessed rather than whatever happens to
    be sitting untracked in the working tree.

    Args:
        base: Compare against the merge-base with this ref, if given.
        staged: Restrict to staged changes.
        cwd: Repository root.

    Raises:
        GitUnavailable: if any underlying git command fails.
    """
    range_args = _diff_range(base, staged, cwd)

    names = _run_git(["diff", "--name-only", *range_args], cwd)
    numstat = _run_git(["diff", "--numstat", *range_args], cwd)
    added = _run_git(["diff", "--diff-filter=A", "--name-only", *range_args], cwd)

    files = [line.strip() for line in names.splitlines() if line.strip()]
    new_files = [line.strip() for line in added.splitlines() if line.strip()]

    if not base and not staged:
        # Untracked files are absent from `git diff HEAD` entirely. They are
        # genuinely part of an uncommitted change, so fold them in here — but
        # only in working-tree mode, where "untracked" is meaningful.
        untracked = _run_git(["ls-files", "--others", "--exclude-standard"], cwd).splitlines()
        extra = [line.strip() for line in untracked if line.strip()]
        files.extend(e for e in extra if e not in files)
        new_files.extend(e for e in extra if e not in new_files)

    return files, [line for line in numstat.splitlines() if line.strip()], new_files


def _parse_numstat(numstat: list[str]) -> tuple[int, int]:
    """Sum added and removed lines from git numstat output, ignoring binaries."""
    added = removed = 0
    for line in numstat:
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        try:
            added += int(parts[0])
            removed += int(parts[1])
        except ValueError:
            continue  # binary files report "-"
    return added, removed


def assess(
    files: list[str],
    numstat: list[str],
    new_files: list[str] | None = None,
) -> RiskAssessment:
    """Score a change and choose a briefing depth.

    Args:
        files: Paths touched by the diff.
        numstat: Raw `git diff --numstat` lines.
        new_files: Paths that did not exist before this change.
    """
    new_files = new_files or []
    added, removed = _parse_numstat(numstat)
    signals: list[Signal] = []

    new_source = [f for f in new_files if SOURCE_EXT.search(f) and not TEST_PATH.search(f)]
    if new_source:
        signals.append(
            Signal(2, f"introduces {len(new_source)} new source file(s) — new surface to maintain")
        )

    security = [f for f in files if SECURITY_PATH.search(f) and not DOC_EXT.search(f)]
    if security:
        signals.append(
            Signal(
                3,
                f"touches security-relevant paths ({', '.join(security[:3])}) "
                "— mistakes here are expensive",
            )
        )

    schema = [f for f in files if SCHEMA_PATH.search(f)]
    if schema:
        signals.append(
            Signal(2, "changes data shape or schema — hard to reverse once data exists")
        )

    deps = [f for f in files if DEPENDENCY_PATH.search(f)]
    if deps:
        signals.append(Signal(2, "changes dependencies — supply chain and upgrade path shift"))

    if removed > 50:
        signals.append(Signal(1, f"removes {removed} lines — behaviour may have left with them"))

    non_test = [f for f in files if not TEST_PATH.search(f)]
    if len(non_test) > 5:
        signals.append(Signal(1, f"spans {len(non_test)} non-test files — the change has reach"))

    if added + removed > 300:
        signals.append(
            Signal(2, f"{added + removed} lines changed — too large to hold in your head")
        )

    score = sum(s.weight for s in signals)
    return RiskAssessment(
        score=score,
        depth=depth_for_score(score),
        files_changed=len(files),
        lines_added=added,
        lines_removed=removed,
        signals=signals,
    )


def assess_working_tree(
    base: str | None = None, staged: bool = False, cwd: Path = PROJECT_ROOT
) -> RiskAssessment:
    """Assess the current repository state.

    Raises:
        GitUnavailable: if the repository cannot be read.
    """
    files, numstat, new_files = collect_diff(base=base, staged=staged, cwd=cwd)
    return assess(files, numstat, new_files)


def render(assessment: RiskAssessment) -> str:
    """Render an assessment as human-readable text."""
    lines = [
        f"Briefing depth: {assessment.depth.upper()}  (score {assessment.score})",
        f"  {assessment.files_changed} files, "
        f"+{assessment.lines_added}/-{assessment.lines_removed}",
    ]
    if assessment.signals:
        lines.append("  Why:")
        lines.extend(f"    [+{s.weight}] {s.reason}" for s in assessment.signals)
    else:
        lines.append("  Why: no elevated signals — a short note is enough.")
    return "\n".join(lines)


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--base", help="Compare against merge-base with this ref")
    parser.add_argument("--staged", action="store_true", help="Assess staged changes only")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args()

    try:
        assessment = assess_working_tree(base=args.base, staged=args.staged)
    except GitUnavailable as exc:
        print(f"Could not assess risk: {exc}", file=sys.stderr)
        print("No briefing depth was determined. Do not treat this as 'light'.", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(assessment.to_dict(), indent=2))
    else:
        print(render(assessment))
    return 0


if __name__ == "__main__":
    sys.exit(main())
