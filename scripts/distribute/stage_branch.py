"""Stage a distribution proposal onto a fresh branch in a target repository.

This is the only module in the distribution package that *writes* to a target. It honors the
load-bearing safety invariants:

- **Never push.** No code path in this module invokes ``git push``.
- **Never touch the target's main.** The proposal is committed to a brand-new branch created
  off the base branch; the base branch itself is never committed to.
- **Never overwrite a pinned trait.** Only ``value`` / ``inert`` files (``package.stageable``)
  are copied; ``collision-pinned`` and ``collision-diverged`` files are left untouched.
- **Leave the target as found.** The original branch is checked back out at the end (and on
  any failure the partial branch is removed), so the working tree is never disturbed.
- **Stay inside the target.** Every destination path is contained within the target root.

The staged commit uses ``--no-verify``: it is a hub-generated *proposal* commit, not a
target-authored change, so the target's pre-commit hook (which expects a target ``/review``
that legitimately does not exist for an externally-staged proposal) must not block it. The
real quality gate is run explicitly by the orchestrator post-stage, and the human reviews the
branch before merging it ("push the proposal, pull the apply").

Usage (library only — invoked by ``.claude/commands/distribute.md``):
    from scripts.distribute.stage_branch import stage
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Ensure project root is on sys.path for module usage.
_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.distribute._git_utils import git_cmd as _git  # noqa: E402
from scripts.distribute.change_package import ChangePackage  # noqa: E402
from scripts.distribute.repo_safety_check import check_clean_tree  # noqa: E402

# Conservative git ref-name allow-list: blocks option injection (leading '-'), traversal ('..'),
# whitespace, and ref-format hazards. Branch names are hub-generated, but we validate anyway.
_REF_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")

DEFAULT_DOC_DIR = "docs/distribution"
# Defense-in-depth cap on caller-supplied ``extra_files`` content (the assent stub is tiny). Bounds
# an upstream logic error that tries to write a runaway blob onto the target branch.
MAX_EXTRA_FILE_BYTES = 512 * 1024
# Model-agnostic on purpose: the hub does not track which live model staged a given proposal here.
COMMIT_TRAILER = "Co-Authored-By: Claude <noreply@anthropic.com>"


@dataclass
class StageResult:
    """Outcome of staging a proposal into a target.

    Attributes:
        target_path: Absolute path of the target repository.
        branch: The fresh branch the proposal was committed to.
        base_branch: The branch the new branch was created off.
        original_branch: The branch checked out before (and restored after) staging.
        files_staged: Relative paths copied onto the staged branch.
        doc_path: Relative path of the written assessment doc.
        commit_sha: SHA of the staging commit.
    """

    target_path: str
    branch: str
    base_branch: str
    original_branch: str
    files_staged: list[str] = field(default_factory=list)
    doc_path: str | None = None
    commit_sha: str | None = None


def _validate_ref_name(branch: str) -> None:
    """Reject branch names that are unsafe as git refs or CLI arguments.

    Args:
        branch: Proposed branch name.

    Raises:
        ValueError: If the name fails the allow-list or contains ``..``.
    """
    if not _REF_NAME_RE.match(branch) or ".." in branch or branch.endswith("/"):
        raise ValueError(f"unsafe branch name: {branch!r}")


def _resolve_within(root: Path, rel_path: str) -> Path:
    """Resolve a relative path and confirm it stays within the root.

    Args:
        root: The (already resolved) containment root.
        rel_path: Relative path to resolve against the root.

    Returns:
        The resolved absolute path.

    Raises:
        ValueError: If the resolved path escapes the root.
    """
    candidate = (root / rel_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"path escapes target root: {rel_path!r}")
    return candidate


def detect_base_branch(target: Path) -> str:
    """Detect the target's main branch: prefer ``main``, then ``master``, else current HEAD.

    Base-branch selection is a *policy* decision the orchestrator should own and pass to
    :func:`stage` explicitly. This helper is exposed so that resolution is visible and testable
    at that layer; :func:`stage` falls back to it only as a convenience for direct callers.

    Args:
        target: Repository working directory.

    Returns:
        The base branch name.

    Raises:
        RuntimeError: If no usable branch can be determined.
    """
    for candidate in ("main", "master"):
        if (
            _git(target, "rev-parse", "--verify", "--quiet", f"refs/heads/{candidate}").returncode
            == 0
        ):
            return candidate
    head = _git(target, "rev-parse", "--abbrev-ref", "HEAD")
    if head.returncode == 0 and head.stdout.strip() and head.stdout.strip() != "HEAD":
        return head.stdout.strip()
    raise RuntimeError("could not determine a base branch for the target")


def _branch_exists(target: Path, branch: str) -> bool:
    """Return True if a local branch already exists."""
    return _git(target, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0


def stage(
    target_path: Path | str,
    package: ChangePackage,
    assessment_doc: str,
    branch: str,
    *,
    template_root: Path | str,
    base_branch: str | None = None,
    doc_relpath: str | None = None,
    exclude_paths: set[str] | None = None,
    extra_files: dict[str, str] | None = None,
) -> StageResult:
    """Stage a distribution proposal onto a fresh branch in the target.

    Copies only ``package.stageable`` (value-unverified + inert) files from the hub to the target,
    writes the advisory assessment doc, and commits to a new branch off the target's main. The
    original branch is restored afterward; on any failure the partial branch is deleted so the
    target is left exactly as found. Never pushes, never commits to the base branch, never copies a
    pinned, diverged, or ``exclude_paths`` (escalated) file.

    The staging commit uses ``--no-verify`` (the target's pre-commit hook expects a target
    ``/review`` a hub proposal cannot have). The caller MUST therefore run the target's quality
    gate post-stage (``repo_safety_check.baseline_gate_green``) before routing the proposal to
    the human — this function delegates that integrity assertion to the orchestrator and does
    not itself validate the staged files.

    Args:
        target_path: Target repository root.
        package: The computed change package (only ``stageable`` items are copied).
        assessment_doc: Markdown body of the advisory assessment doc.
        branch: Fresh branch name to create (must not already exist).
        template_root: Hub (template) repository root to copy files from.
        base_branch: Branch to create off. The orchestrator should pass this explicitly; falls
            back to :func:`detect_base_branch` (main/master/HEAD) for direct callers.
        doc_relpath: Where to write the assessment doc (defaults to
            ``docs/distribution/<branch>.md``).
        exclude_paths: Stageable files to refuse to copy even though they are in
            ``package.stageable`` — **mechanical backstop** for the escalate-only reclassification
            bridge. A ``value-unverified`` file the interpretation room escalated to
            ``collision-diverged`` is passed here so it is never physically written to the branch,
            even if a future orchestrator forgets to halt. The guarantee is mechanical, not prose
            (the override is a ``RouteDecision``, not a mutation of ``classification``).
        extra_files: Caller-supplied ``{relpath: content}`` written onto the branch as **deploy
            step zero**, before any framework file is copied (R8 / Steward condition 3). The APPLY
            route uses this for the human-authored assent stub (``framework-lineage.yaml``) so the
            consent record lands *inside the back-out branch* — deleting the branch reverts it,
            leaving no orphaned consent record on a repo that received nothing else. Each path is
            contained within the target by :func:`_resolve_within`.

    Returns:
        A :class:`StageResult`.

    Raises:
        ValueError: On an unsafe branch name, an existing branch, or a path escape.
        RuntimeError: If the target is unsafe to stage into, or a git operation fails.
    """
    target = Path(target_path).resolve()
    hub_root = Path(template_root).resolve()
    _validate_ref_name(branch)

    # Defense in depth: refuse to write into an unsafe tree even if called directly. The DEPLOY
    # gate is the *separable* clean-tree check (R7), NOT the fused repo_safety_check — a greenfield
    # APPLY target has no manifest and is not opted in, so the fused gate would reject it even when
    # clean. Consent on the APPLY route is enforced upstream (the R8 assent preflight); here we
    # guard only that the tree is safe to write into, which is identical for both routes.
    clean = check_clean_tree(target)
    if not clean.is_clean:
        raise RuntimeError(f"target not safe to stage into: {clean.blockers}")

    if _branch_exists(target, branch):
        raise ValueError(f"branch already exists: {branch}")

    base = base_branch or detect_base_branch(target)
    original_branch = clean.branch or base
    # All three refs flow into `git checkout` as positional args — validate every one
    # (not just the hub-generated branch) to close the option-injection surface.
    _validate_ref_name(base)
    _validate_ref_name(original_branch)
    doc_rel = doc_relpath or f"{DEFAULT_DOC_DIR}/{branch.replace('/', '-')}.md"
    doc_dest = _resolve_within(
        target, doc_rel
    )  # resolve + validate ONCE; reused below (no TOCTOU)

    # Create the fresh branch off base; from here we must restore on failure.
    _git(target, "checkout", "-b", branch, base, check=True)

    try:
        files_staged: list[str] = []
        excluded = exclude_paths or set()

        # Deploy step zero (R8 / Steward condition 3): write caller-supplied files (e.g. the APPLY
        # human-authored assent stub) FIRST, contained within the target. They live on this branch
        # only, so deleting the branch on back-out reverts them — no orphaned consent record.
        for rel, content in (extra_files or {}).items():
            if len(content.encode("utf-8")) > MAX_EXTRA_FILE_BYTES:
                raise ValueError(
                    f"extra_files content for {rel!r} exceeds {MAX_EXTRA_FILE_BYTES} bytes"
                )
            dest = _resolve_within(target, rel)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            files_staged.append(rel)

        for item in package.stageable:
            # Mechanical backstop for the escalate-only bridge: never copy an escalated file, even
            # if it is still in package.stageable (the override is a RouteDecision, not mutation).
            if item.file_path in excluded:
                continue
            # Contain both sides: a crafted file_path must not read outside the hub or write
            # outside the target.
            src = _resolve_within(hub_root, item.file_path)
            if not src.is_file():
                continue
            dest = _resolve_within(target, item.file_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            files_staged.append(item.file_path)

        # doc_dest was resolved + validated above — do not re-resolve (closes the TOCTOU window).
        doc_dest.parent.mkdir(parents=True, exist_ok=True)
        doc_dest.write_text(assessment_doc, encoding="utf-8")

        _git(target, "add", "-A", check=True)
        message = (
            f"chore(framework): stage distribution proposal [{branch}]\n\n"
            f"Hub-staged framework update — UNMERGED, UNPUSHED, off {base}.\n"
            f"Advisory only; review before merging. {len(files_staged)} file(s) staged.\n\n"
            f"{COMMIT_TRAILER}"
        )
        # --no-verify: a hub-generated proposal commit; the target's own quality gate is run
        # explicitly by the orchestrator post-stage, and the human reviews before merging.
        _git(target, "commit", "--no-verify", "-m", message, check=True)
        commit_sha = _git(target, "rev-parse", branch).stdout.strip() or None
    except (subprocess.CalledProcessError, OSError, ValueError):
        # Restore the target exactly as found. `branch -D` runs in `finally` so the partial
        # branch is removed even if the restore checkout itself fails — the target must never
        # be left sitting on a half-staged branch.
        try:
            _git(target, "checkout", "--force", original_branch)
        finally:
            _git(target, "branch", "-D", branch)
        raise

    # Restore the original branch; the staged branch retains the commit.
    _git(target, "checkout", original_branch, check=True)

    return StageResult(
        target_path=str(target),
        branch=branch,
        base_branch=base,
        original_branch=original_branch,
        files_staged=files_staged,
        doc_path=doc_rel,
        commit_sha=commit_sha,
    )
