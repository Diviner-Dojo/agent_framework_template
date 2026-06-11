"""Safety preflight for ``/apply-framework`` (and the legacy ``/distribute`` UPDATE route).

A target on the **UPDATE** route is only eligible to receive a staged framework update when
**both** hold:

1. **Opt-in** — the target declares ``custodian.accepts_distribution: true`` in its own
   ``framework-lineage.yaml`` (per-instance assent; same absolute shape as a pinned trait).
2. **Safe** — its git working tree is clean, HEAD is on a branch (not detached), no merge /
   rebase / cherry-pick / revert / bisect is in progress, and a lineage manifest exists.

A target failing either condition is **skipped on the write path** — recorded and reported,
never written to. ``--dry-run`` callers still compute the report and surface the predicted
``SKIPPED`` route; the gate only blocks the actual ``stage_branch`` write.

**Decomposition (R7).** The fused :func:`repo_safety_check` (= opt-in AND clean-tree AND
manifest-present) blocks *every* greenfield target, so the gate is decomposed into independent,
separately-callable checks: :func:`check_clean_tree` (git state alone — the **DEPLOY gate** for
both routes), :func:`manifest_presence`, and a **pluggable consent preflight**:
:func:`update_consent` (the UPDATE opt-in hard gate, unchanged) and :func:`apply_consent` /
:func:`apply_assent_preflight` (the APPLY route, R8). The deploy path gates on **clean-tree
alone**, never the fused ``can_proceed``; :func:`repo_safety_check` is retained (now composed from
the parts) so the UPDATE preflight is unchanged.

The optional baseline quality-gate check (:func:`baseline_gate_green`) is kept separate so
the cheap git/manifest preflight stays fast and unit-testable; the orchestrator runs the
gate only on the live (non-dry-run) path. On the APPLY route it **defaults to skip** (R2 /
Steward condition 4) — an arbitrary target's ``quality_gate.py`` is a code-execution surface.

Usage:
    python scripts/distribute/repo_safety_check.py /path/to/target
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
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


@dataclass
class CleanTreeReport:
    """Result of the **separable** clean-tree check (R7) — the DEPLOY gate for both routes.

    The deploy path gates on this alone (``is_clean``), never the fused
    :attr:`SafetyReport.can_proceed`, so a greenfield target (which has no manifest and no opt-in)
    is not blocked by checks that only make sense on the UPDATE route.

    Attributes:
        target_path: Absolute path of the target repository.
        is_clean: True iff the working tree is clean and git state is undisturbed.
        blockers: Human-readable reasons the tree is not deploy-safe (empty when clean).
        branch: The checked-out branch name, or None if detached / undetermined.
    """

    target_path: str
    is_clean: bool
    blockers: list[str] = field(default_factory=list)
    branch: str | None = None


@dataclass(frozen=True)
class ConsentResult:
    """Verdict of a consent preflight — the pluggable per-route assent gate (R7/R8).

    Attributes:
        ok: True iff consent is satisfied for the route.
        reason: Short human-readable justification (safe to log / display; no target content).
    """

    ok: bool
    reason: str


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


def check_clean_tree(target_path: Path | str) -> CleanTreeReport:
    """The **separable** clean-tree check (R7) — the DEPLOY gate for both routes.

    Independent of opt-in and manifest-presence: a clean greenfield repo (no manifest, no opt-in)
    passes this even though it would fail the fused :func:`repo_safety_check`. The deploy path
    gates on this alone. Read-only.

    Args:
        target_path: Path to the target repository root.

    Returns:
        A :class:`CleanTreeReport`. Inspect ``is_clean``.
    """
    target = Path(target_path).resolve()
    if not target.is_dir():
        return CleanTreeReport(
            target_path=str(target),
            is_clean=False,
            blockers=[f"target path is not a directory: {target}"],
        )
    blockers, branch = _check_git_state(target)
    return CleanTreeReport(
        target_path=str(target),
        is_clean=len(blockers) == 0,
        blockers=blockers,
        branch=branch,
    )


def manifest_presence(target_path: Path | str) -> tuple[dict | None, list[str]]:
    """Read the target's lineage manifest as a **separable** check (R7).

    Args:
        target_path: Path to the target repository root.

    Returns:
        A tuple of (manifest_or_None, blockers). ``blockers`` is non-empty when the manifest is
        missing (greenfield — not an error here, just absent) or unreadable (fail closed).
    """
    target = Path(target_path).resolve()
    blockers: list[str] = []
    manifest_path = target / MANIFEST_NAME
    try:
        manifest = manifest_read(manifest_path)
    except FileNotFoundError:
        blockers.append(f"no lineage manifest ({MANIFEST_NAME}) — target is not framework-tracked")
        manifest = None
    except (ValueError, OSError, yaml.YAMLError) as exc:
        blockers.append(f"lineage manifest unreadable: {exc}")
        manifest = None
    return manifest, blockers


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

    if not target.is_dir():
        return SafetyReport(
            target_path=str(target),
            opted_in=False,
            is_safe=False,
            blockers=[f"target path is not a directory: {target}"],
        )

    # Composed from the separable checks (R7): manifest presence + opt-in consent + clean tree.
    manifest, manifest_blockers = manifest_presence(target)
    opted_in = update_consent(manifest).ok

    accept_paths: list[str] = []
    deny_paths: list[str] = []
    if manifest is not None:
        custodian = manifest.get("custodian") or {}
        if isinstance(custodian, dict):
            accept_paths = list(custodian.get("accept_paths") or [])
            deny_paths = list(custodian.get("deny_paths") or [])

    clean = check_clean_tree(target)
    blockers = manifest_blockers + clean.blockers

    return SafetyReport(
        target_path=str(target),
        opted_in=opted_in,
        is_safe=len(blockers) == 0,
        blockers=blockers,
        accept_paths=accept_paths,
        deny_paths=deny_paths,
        branch=clean.branch,
    )


def update_consent(manifest: dict | None) -> ConsentResult:
    """UPDATE-route consent: the opt-in HARD GATE (unchanged).

    A derived project consents to receiving framework updates by declaring
    ``custodian.accepts_distribution: true`` in its own manifest — only a strict boolean ``True``
    opts in (a string ``"true"`` / integer ``1`` do not).

    Args:
        manifest: The parsed target manifest, or None when absent/unreadable.

    Returns:
        A :class:`ConsentResult`.
    """
    if not isinstance(manifest, dict):
        return ConsentResult(False, "no lineage manifest — target is not framework-tracked")
    custodian = manifest.get("custodian") or {}
    if isinstance(custodian, dict) and custodian.get("accepts_distribution") is True:
        return ConsentResult(True, "custodian.accepts_distribution: true")
    return ConsentResult(False, "custodian.accepts_distribution is not true (opt-in HARD GATE)")


def _is_meaningful_name(value: str) -> bool:
    """True iff ``value`` contains at least one visible character a human could read as a name.

    ``str.strip()`` only removes Unicode *whitespace*; invisible format characters — zero-width
    space (U+200B), ZWNJ/ZWJ (U+200C/D), BOM (U+FEFF), soft hyphen (U+00AD), directional marks
    (U+200E/F) — survive it, so a visually-blank string would satisfy a bare emptiness check and
    forge a blank "human-authored" assent (REV-20260611 security F1). A meaningful name needs at
    least one character outside the Unicode separator (``Z*``) and control/format (``C*``)
    categories.
    """
    return any(unicodedata.category(c)[0] not in ("Z", "C") for c in value)


def apply_assent_preflight(
    primary_human: object,
    accepts_distribution: object = True,
) -> ConsentResult:
    """APPLY-route consent preflight (R8 option ii, Steward condition 2) — **FAIL CLOSED**.

    Lineage-absence is *inversely* correlated with ownership, so the APPLY route (the easiest to
    misaim at a repo the operator does not own) requires the **strongest** explicit assent: a
    **non-null, human-authored** ``primary_human`` **AND** ``accepts_distribution: true``. A null,
    empty, or whitespace-only ``primary_human`` (the ``lineage_init`` default) does **not** satisfy
    the gate — deploy is blocked. This is the concrete, testable
    deploy preflight the spec requires (not prose).

    Args:
        primary_human: The named human authoring the assent (must be a non-empty string).
        accepts_distribution: Must be the boolean ``True``.

    Returns:
        A :class:`ConsentResult`.
    """
    human = primary_human if isinstance(primary_human, str) else None
    if not human or not human.strip() or not _is_meaningful_name(human):
        return ConsentResult(
            False,
            "primary_human is null/empty/invisible — APPLY requires a named human author "
            "(fail closed; invisible-only Unicode does not name a human)",
        )
    if accepts_distribution is not True:
        return ConsentResult(False, "accepts_distribution is not true")
    return ConsentResult(
        True, f"human-authored assent: primary_human={human.strip()!r}, accepts_distribution: true"
    )


def apply_consent(manifest_or_stub: dict | None) -> ConsentResult:
    """APPLY-route consent read from an assent stub / manifest dict (R8) — delegates fail-closed.

    Reads ``custodian.primary_human`` + ``custodian.accepts_distribution`` from a built stub (or a
    target manifest) and validates them via :func:`apply_assent_preflight`. This is what the deploy
    preflight calls against the stub written as deploy step zero.

    Args:
        manifest_or_stub: The parsed assent stub / manifest, or None.

    Returns:
        A :class:`ConsentResult`.
    """
    if not isinstance(manifest_or_stub, dict):
        return ConsentResult(False, "no assent stub / manifest")
    custodian = manifest_or_stub.get("custodian") or {}
    if not isinstance(custodian, dict):
        return ConsentResult(False, "custodian block malformed")
    return apply_assent_preflight(
        custodian.get("primary_human"), custodian.get("accepts_distribution")
    )


def build_assent_stub(
    primary_human: object,
    *,
    project_name: str = "unnamed-project",
    template_version: str = "3.5.0",
) -> dict:
    """Build the minimal human-authored assent stub written into a greenfield target (R8).

    The stub is a minimal but schema-valid ``framework-lineage.yaml`` whose ``custodian`` block
    records the per-instance assent — converging the APPLY and UPDATE routes onto **one**
    human-authored assent record. It is written **inside the branched deploy** as step zero (R7 /
    Steward condition 3), so deleting the back-out branch reverts it: a back-out leaves no orphaned
    consent record on a repo that received nothing else.

    This builder is deliberately *dumb* — it records whatever ``primary_human`` it is given
    (including a null one). The **fail-closed gate is :func:`apply_consent` /
    :func:`apply_assent_preflight`**, not this function: deploy validates the stub before writing
    anything else.

    Args:
        primary_human: The named human authoring the assent (or None — which the preflight blocks).
        project_name: Human-readable project name for the stub's ``instance.name``.
        template_version: The hub framework version this APPLY came from.

    Returns:
        A manifest dictionary ready to ``yaml.dump`` into the target as ``framework-lineage.yaml``.
    """
    now = datetime.now(UTC).isoformat()
    human = (
        primary_human.strip()
        if isinstance(primary_human, str)
        and primary_human.strip()
        and _is_meaningful_name(primary_human)
        else None
    )
    return {
        "schema_version": "1.0",
        "lineage_id": str(uuid.uuid4()),
        "serial": 0,
        "instance": {
            "name": project_name,
            "version": f"1.0.0+upstream.{template_version}",
            "type": "derived",
            "created_at": now,
        },
        "drift": {"status": "current", "divergence_distance": 0},
        "pinned_traits": [],
        "custodian": {
            "primary_human": human,
            "accepts_distribution": True,
            "assent_recorded_at": now,
            "assent_route": "apply-framework",
            "approval_required_for": [
                "template_modification",
                "principle_change",
                "agent_restructuring",
            ],
        },
    }


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
