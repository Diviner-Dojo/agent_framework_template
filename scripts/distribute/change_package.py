"""Compute the change package for a distribution target.

Given the hub's *offer set* (the framework files a framework update wants to propagate),
classify each file against a single target so the orchestrator and assessment room know what
is safe to stage, what must be dropped, and what needs human-mediated assessment.

Classifications:

- ``value``            — RESERVED for v1.1: an overwrite *proven* safe against a hub-side ancestor
                          (silent, no per-file detail). NOT produced in v1 — there is no reliable
                          ancestor yet — no overwrite is provably safe (see ``value-unverified``).
- ``value-unverified`` — the hub's version differs and the target shows no *proven* divergence
                          (drift ``current`` or untracked) → an overwrite the hub **cannot prove
                          safe**. The mechanical safety floor (finding B1): ``current`` may be a
                          re-baselined local edit and untracked may be a ``tracked_paths``-narrowed
                          file, so neither proves the target's copy came untouched from the hub.
                          **Stageable but flagged** — staged for an easy merge yet always surfaced
                          with per-file detail in the assessment doc; never a silent safe update.
- ``inert``            — target lacks the file entirely → a pure addition (no overwrite); safe to
                          stage even if the target won't use it yet (goal A: stage inert features).
- ``collision-pinned`` — the file matches one of the target's ``pinned_traits`` → **dropped**,
                          never staged (pinned traits are absolute).
- ``collision-diverged``— the target has deliberately modified or deleted the file relative to its
                          baseline and the hub's version differs → **assess** (may clobber a
                          deliberate divergence); never auto-staged.
- ``current``          — target already matches the hub → nothing to do.
- ``denied`` / ``not-accepted`` — excluded by the target's per-path ``deny_paths`` /
                          ``accept_paths``.
- ``unavailable``      — the offered file does not exist in the hub (defensive; should not occur).

Divergence is read through an injected :class:`Baseline` (R4) — the *single* floor primitive runs
against two interchangeable baselines so the UPDATE and APPLY routes can never diverge:

- :class:`LineageBaseline` (the UPDATE route) reads the lineage engine
  (:func:`scripts.lineage.drift.drift_scan`) + the target manifest. The drift baseline is the
  target's *mutable* DB, NOT a hub-target ancestor, so it cannot *prove* an overwrite is safe — any
  overwrite of differing content fails safe to ``value-unverified`` (the floor) until v1.1 adds
  hub-side ancestor tracking. Provable divergence (modified / added / deleted) is
  ``collision-diverged``; a missing baseline never silently passes.
- :class:`OnDiskBaseline` (the greenfield APPLY route) has **no** lineage history and **no**
  manifest, so it reports no provable divergence and no pinned/accept/deny policy. Every existing
  target file at a framework path is therefore an unprovable overwrite (``value-unverified``); a
  path the target lacks is a pure addition (``inert``). This is the structural reason the B1 floor
  extends to greenfield unchanged — it is the same primitive, just a baseline with no ancestor.

Usage:
    python scripts/distribute/change_package.py <template_root> <target> --offer FILE [FILE ...]
"""

from __future__ import annotations

import argparse
import fnmatch
import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

# Ensure project root is on sys.path for both CLI and module usage.
_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.lineage._utils import (  # noqa: E402
    collect_framework_files,
    hash_file,
    list_untracked_framework_files,
)
from scripts.lineage.drift import FileDrift, drift_scan  # noqa: E402
from scripts.lineage.manifest import manifest_read  # noqa: E402

MANIFEST_NAME = "framework-lineage.yaml"

# Bound the greenfield offer set (R4): the framework corpus is enumerated and CAPPED, never an
# implicit "everything". A pathological hub tree must not turn an APPLY into an unbounded copy.
MAX_GREENFIELD_OFFER = 5000

# Classifications that stage_branch will actually write to the staged branch. ``value-unverified``
# is stageable but ALWAYS surfaced with per-file detail (the floor stages it, never silently).
# ``value`` is reserved for v1.1 (ancestor-proven) and not produced in v1.
STAGEABLE = ("value", "value-unverified", "inert")
# Classifications dropped (never written) for safety / opt-in reasons.
DROPPED = ("collision-pinned", "denied", "not-accepted")

# Interpretation verdicts (R4): the room's per-file judgment on a ``value-unverified`` overwrite.
# ESCALATING verdicts trip the escalate-only reclassification bridge (toward collision-diverged);
# BENIGN verdicts leave the floor's value-unverified route unchanged (still staged + flagged).
ESCALATING_VERDICTS = ("behavioral-blast-radius", "likely-deliberate")
BENIGN_VERDICTS = ("cosmetic", "benign")

# Bound per-path accept/deny globs at load (B3) — fnmatch compiles a glob to a regex, so an
# unbounded list of pathological patterns from a hostile or oversized manifest is a matching-cost
# DoS surface.
MAX_PER_PATH_PATTERNS = 500
MAX_PATTERN_LEN = 500


@dataclass
class ChangeItem:
    """Classification of a single offered file against one target.

    Attributes:
        file_path: Relative, forward-slash path of the offered file.
        classification: One of value / value-unverified / inert / collision-pinned /
            collision-diverged / current / denied / not-accepted / unavailable.
        hub_hash: SHA-256 of the hub's copy, or None if absent in the hub.
        target_hash: SHA-256 of the target's copy, or None if the target lacks it.
        drift_status: The target's drift status for this file (current / modified / added /
            deleted / pinned), or None if untracked.
        reason: Short human-readable justification for the classification.
    """

    file_path: str
    classification: str
    hub_hash: str | None
    target_hash: str | None
    drift_status: str | None
    reason: str


@dataclass
class ChangePackage:
    """The full classification of an offer set against one target.

    Attributes:
        target_path: Absolute path of the target repository.
        items: Per-file classifications.
    """

    target_path: str
    items: list[ChangeItem] = field(default_factory=list)

    @property
    def stageable(self) -> list[ChangeItem]:
        """Files that stage_branch will write (value-unverified + inert; value reserved v1.1)."""
        return [i for i in self.items if i.classification in STAGEABLE]

    @property
    def pinned_dropped(self) -> list[ChangeItem]:
        """Files dropped because they collide with a pinned trait."""
        return [i for i in self.items if i.classification == "collision-pinned"]

    @property
    def diverged(self) -> list[ChangeItem]:
        """Files needing human-mediated assessment (deliberate divergence collision)."""
        return [i for i in self.items if i.classification == "collision-diverged"]

    @property
    def requires_interpretation(self) -> list[ChangeItem]:
        """Overwriting files the floor flagged (``value-unverified``).

        Staged but never silent: the hub would overwrite existing target content and cannot prove
        it safe against an ancestor (B1), so each is surfaced with per-file interpretation in the
        assessment doc. The interpretation *explains* these; it never decides whether to flag them
        (the mechanical floor already did, by construction).
        """
        return [i for i in self.items if i.classification == "value-unverified"]

    @property
    def excluded(self) -> list[ChangeItem]:
        """Files excluded by the target's per-path accept/deny rules."""
        return [i for i in self.items if i.classification in ("denied", "not-accepted")]

    def has_unmediable_candidates(self) -> bool:
        """True if any file needs assessment (a collision-diverged candidate exists).

        A package with no diverged candidates is *obviously inert* and qualifies for the
        Growth-brake fast-path (single risk-referee instead of the full assessment room).
        (`PHILOSOPHY.md`, *Growth has a brake* — a numbered principle until v3.6.)
        """
        return len(self.diverged) > 0

    def needs_interpretation(self) -> bool:
        """True if the floor flagged any overwrite (``value-unverified``).

        Growth-brake tiering (`PHILOSOPHY.md`, *Growth has a brake*): when this is True but
        ``has_unmediable_candidates`` is False, the
        single referee interprets the flagged overwrites (fast-path); when a collision-diverged
        file is also present, the full room handles both.
        """
        return len(self.requires_interpretation) > 0

    def counts(self) -> dict[str, int]:
        """Count items per classification — the only package detail safe to put in an ntfy.

        Returns a content-free summary (counts, never file bodies) honoring cross-repo
        confidentiality.
        """
        result: dict[str, int] = {}
        for item in self.items:
            result[item.classification] = result.get(item.classification, 0) + 1
        return result


def _matches_any(rel_path: str, patterns: list[str]) -> bool:
    """Return True if a relative path matches any glob or directory-prefix pattern.

    A trailing-slash pattern (``.claude/``) matches the directory and everything under it.
    Other patterns are matched with :func:`fnmatch.fnmatch` (``*`` spans path separators).

    Args:
        rel_path: Forward-slash relative path to test.
        patterns: Glob / directory-prefix patterns.

    Returns:
        True if the path matches at least one pattern.
    """
    for raw in patterns:
        pattern = str(raw).replace("\\", "/")
        if pattern.endswith("/"):
            if rel_path == pattern[:-1] or rel_path.startswith(pattern):
                return True
        elif fnmatch.fnmatch(rel_path, pattern):
            return True
    return False


def _load_pinned_patterns(manifest: dict) -> list[str]:
    """Extract pinned-trait path patterns from a target manifest.

    Args:
        manifest: Parsed target ``framework-lineage.yaml``.

    Returns:
        List of pinned path patterns (prefix-matched, like the lineage drift engine).
    """
    patterns: list[str] = []
    for trait in manifest.get("pinned_traits", []) or []:
        if isinstance(trait, dict) and trait.get("path"):
            patterns.append(str(trait["path"]))
    return patterns


def _is_pinned(rel_path: str, pinned_patterns: list[str]) -> bool:
    """Check whether a path matches any pinned-trait pattern (prefix or exact match)."""
    return any(rel_path == p or rel_path.startswith(p) for p in pinned_patterns)


def _bound_patterns(patterns: object) -> list[str]:
    """Bound per-path accept/deny globs at load (B3).

    Keeps only string entries no longer than ``MAX_PATTERN_LEN`` and caps the total at
    ``MAX_PER_PATH_PATTERNS`` — fail-safe against a hostile or oversized manifest turning fnmatch
    into a matching-cost DoS. Dropping (rather than raising) keeps ``/distribute`` fail-soft per
    target.

    Args:
        patterns: The raw value from the manifest (any type; only a list of strings is honored).

    Returns:
        A bounded list of glob patterns.
    """
    if not isinstance(patterns, list):
        return []
    out: list[str] = []
    for p in patterns:
        if isinstance(p, str) and len(p) <= MAX_PATTERN_LEN:
            out.append(p)
        if len(out) >= MAX_PER_PATH_PATTERNS:
            break
    return out


class Baseline(Protocol):
    """The target's prior-version oracle for the floor decision (R4) — one floor, two baselines.

    A :class:`Baseline` supplies everything the shared floor primitive (:func:`_classify`) needs
    about *the target* that is not a direct disk read of the offered file: the provable-divergence
    status of a path and the manifest-derived per-target policy (pinned traits / accept / deny).
    Two implementations feed the *same* primitive — :class:`LineageBaseline` (UPDATE) and
    :class:`OnDiskBaseline` (greenfield APPLY) — so the B1 floor lives in one auditable place and
    route divergence is structurally impossible.

    Attributes:
        pinned_patterns: Target pinned-trait path patterns (absolute drops).
        accept_paths: Per-path allow-list globs (empty = allow all, subject to deny).
        deny_paths: Per-path deny-list globs.
    """

    pinned_patterns: list[str]
    accept_paths: list[str]
    deny_paths: list[str]

    def divergence(self, rel_path: str) -> str | None:
        """Return the target's *provable* drift status for a path, or None.

        Only ``"modified"`` / ``"added"`` / ``"deleted"`` (and ``"pinned"``) are *provable* — they
        convene assessment. ``"current"`` / ``None`` do NOT prove the target's copy descends
        untouched from the hub (finding B1), so a differing overwrite under them is the floor's
        ``value-unverified``, never a silent safe update.
        """
        ...


@dataclass
class LineageBaseline:
    """The UPDATE-route baseline: lineage drift + the target's manifest policy (R4).

    Unchanged behavior relative to the pre-R4 inline path — it just names the abstraction the floor
    consults so the greenfield route can swap in :class:`OnDiskBaseline`.

    Attributes:
        drift_map: Target drift status keyed by relative path (from :func:`drift_scan`).
        pinned_patterns: Pinned-trait patterns from the target manifest.
        accept_paths: Bounded per-path allow-list globs from the manifest custodian block.
        deny_paths: Bounded per-path deny-list globs from the manifest custodian block.
    """

    drift_map: dict[str, FileDrift]
    pinned_patterns: list[str] = field(default_factory=list)
    accept_paths: list[str] = field(default_factory=list)
    deny_paths: list[str] = field(default_factory=list)

    def divergence(self, rel_path: str) -> str | None:
        """Read the drift status for a path from the lineage scan, or None if untracked."""
        drift = self.drift_map.get(rel_path)
        return drift.drift_status if drift else None

    @classmethod
    def from_target(
        cls, target_root: Path, *, manifest_path: Path, db_path: Path
    ) -> LineageBaseline:
        """Build a baseline from a target's manifest + a drift scan.

        Args:
            target_root: Target repository root.
            manifest_path: Path to the target ``framework-lineage.yaml``.
            db_path: Path to the target metrics DB (the drift baseline source).

        Returns:
            A populated :class:`LineageBaseline`.

        Raises:
            FileNotFoundError: If the target manifest does not exist (fail closed — never silently
                fall back to a greenfield read of a framework-tracked target).
        """
        manifest = manifest_read(manifest_path)
        pinned = _load_pinned_patterns(manifest)
        custodian = manifest.get("custodian") or {}
        accept = (
            _bound_patterns(custodian.get("accept_paths")) if isinstance(custodian, dict) else []
        )
        deny = _bound_patterns(custodian.get("deny_paths")) if isinstance(custodian, dict) else []
        drift_results = drift_scan(
            manifest_path=manifest_path, project_root=target_root, db_path=db_path
        )
        drift_map = {f.file_path: f for f in drift_results}
        return cls(
            drift_map=drift_map, pinned_patterns=pinned, accept_paths=accept, deny_paths=deny
        )


@dataclass
class OnDiskBaseline:
    """The greenfield APPLY-route baseline: no lineage history, no manifest (R4).

    There is no recorded ancestor, so NOTHING is provably diverged: every existing target file at
    a framework path is an overwrite the hub cannot prove safe (``value-unverified``, the floor),
    and a path the target lacks is a pure addition (``inert``). No manifest means no pinned /
    accept / deny policy. This is the structural reason the B1 floor extends to greenfield
    *unchanged*: the floor primitive is identical; only the baseline (ancestor-less) differs.
    """

    pinned_patterns: list[str] = field(default_factory=list)
    accept_paths: list[str] = field(default_factory=list)
    deny_paths: list[str] = field(default_factory=list)

    def divergence(self, rel_path: str) -> str | None:
        """Greenfield has no ancestor — no path is ever provably diverged."""
        return None


def _classify(
    rel_path: str,
    *,
    hub_root: Path,
    target_root: Path,
    baseline: Baseline,
) -> ChangeItem:
    """Classify a single offered file against the target — the one shared floor primitive (R4).

    Route-agnostic by construction: it reads the offered file from the hub and the target's copy
    from disk, and consults the injected :class:`Baseline` for divergence + per-path policy. The
    floor (an unprovable overwrite → ``value-unverified``) is decided here, once, for both the
    UPDATE (:class:`LineageBaseline`) and greenfield (:class:`OnDiskBaseline`) routes.

    Args:
        rel_path: Forward-slash relative path of the offered file.
        hub_root: Hub (template) repository root.
        target_root: Target repository root.
        baseline: The injected prior-version oracle (divergence + pinned/accept/deny policy).

    Returns:
        A :class:`ChangeItem`.
    """
    drift_status = baseline.divergence(rel_path)
    pinned_patterns = baseline.pinned_patterns
    accept_paths = baseline.accept_paths
    deny_paths = baseline.deny_paths

    hub_file = hub_root / rel_path
    if not hub_file.is_file():
        return ChangeItem(rel_path, "unavailable", None, None, drift_status, "not present in hub")
    hub_hash = hash_file(hub_file)

    # Per-path opt-in granularity (deny takes precedence over accept). Excluded here, before the
    # target disk read, so target_hash is intentionally None on these gates (the file is dropped).
    if _matches_any(rel_path, deny_paths):
        return ChangeItem(rel_path, "denied", hub_hash, None, drift_status, "matches deny_paths")
    if accept_paths and not _matches_any(rel_path, accept_paths):
        return ChangeItem(
            rel_path,
            "not-accepted",
            hub_hash,
            None,
            drift_status,
            "not in accept_paths allow-list",
        )

    # Pinned traits are absolute — dropped before any update is considered.
    if _is_pinned(rel_path, pinned_patterns) or drift_status == "pinned":
        return ChangeItem(
            rel_path, "collision-pinned", hub_hash, None, drift_status, "matches a pinned trait"
        )

    target_file = target_root / rel_path
    target_hash = hash_file(target_file) if target_file.is_file() else None

    # Target lacks the file: pure addition (inert) unless it was a deliberate deletion (diverged).
    if target_hash is None:
        if drift_status == "deleted":
            return ChangeItem(
                rel_path,
                "collision-diverged",
                hub_hash,
                None,
                drift_status,
                "target deliberately removed this file; re-adding may clobber that decision",
            )
        return ChangeItem(
            rel_path, "inert", hub_hash, None, drift_status, "new file for the target"
        )

    if target_hash == hub_hash:
        return ChangeItem(
            rel_path, "current", hub_hash, target_hash, drift_status, "already in sync"
        )

    # Hub differs from target. Provable divergence → assess.
    if drift_status in ("modified", "added", "deleted"):
        return ChangeItem(
            rel_path,
            "collision-diverged",
            hub_hash,
            target_hash,
            drift_status,
            "target diverged from baseline and the hub also changed it",
        )
    # Mechanical safety floor (B1): an overwrite we cannot PROVE safe. drift_status is "current" or
    # None, but neither proves the target's copy descends untouched from the hub's offered version
    # ("current" may be a re-baselined local edit; None may be a tracked_paths-narrowed file).
    # Until v1.1 adds hub-side ancestor tracking, fail safe to value-unverified — stageable but
    # always surfaced with detail — never a silent "value".
    return ChangeItem(
        rel_path,
        "value-unverified",
        hub_hash,
        target_hash,
        drift_status,
        "overwrites target content; cannot prove safe against a hub ancestor (B1) — flagged",
    )


def compute_package(
    template_root: Path | str,
    target_path: Path | str,
    offer_set: list[str],
    *,
    db_path: Path | None = None,
    manifest_path: Path | None = None,
) -> ChangePackage:
    """Classify an offer set against a single target repository.

    Args:
        template_root: Hub (template) repository root.
        target_path: Target repository root.
        offer_set: Relative, forward-slash paths the hub offers to propagate.
        db_path: Target metrics DB (defaults to ``<target>/metrics/evaluation.db``).
        manifest_path: Target manifest (defaults to ``<target>/framework-lineage.yaml``).

    Returns:
        A :class:`ChangePackage` describing each offered file's classification.

    Raises:
        FileNotFoundError: If the target manifest does not exist.
    """
    hub_root = Path(template_root).resolve()
    target_root = Path(target_path).resolve()
    m_path = manifest_path or (target_root / MANIFEST_NAME)
    d_path = db_path or (target_root / "metrics" / "evaluation.db")

    baseline = LineageBaseline.from_target(target_root, manifest_path=m_path, db_path=d_path)
    items = [
        _classify(
            rel.replace("\\", "/"),
            hub_root=hub_root,
            target_root=target_root,
            baseline=baseline,
        )
        for rel in offer_set
    ]
    return ChangePackage(target_path=str(target_root), items=items)


def greenfield_offer_set(
    template_root: Path | str, *, cap: int = MAX_GREENFIELD_OFFER
) -> list[str]:
    """The hub's framework corpus as a bounded, sorted greenfield offer set (R4).

    Enumerates the framework-path corpus (``FRAMEWORK_PATHS``: ``.claude/``, ``scripts/``,
    ``CLAUDE.md``, ``docs/templates/``, ``docs/adr/``) from the hub and CAPS it. The greenfield
    APPLY route offers exactly this set — explicitly bounded and enumerated, never an implicit
    "everything" — so a pathological hub tree cannot turn an APPLY into an unbounded copy.

    The corpus now respects ``.gitignore`` (ADR-0025), so the cap is a fail-loud bound on a
    *legitimately*-large corpus — no longer a silent absorber of gitignored pollution. R4
    makes both anomalous outcomes loud, and R3 surfaces framework work that won't propagate.

    Args:
        template_root: Hub (template) repository root.
        cap: Maximum number of files to offer (defaults to :data:`MAX_GREENFIELD_OFFER`).

    Returns:
        A sorted list of relative, forward-slash framework paths (at most ``cap``).

    Raises:
        ValueError: if the corpus exceeds ``cap`` — fail loud, never silently truncate (R4).
    """
    root = Path(template_root)
    files = sorted(collect_framework_files(root).keys())

    if len(files) > cap:
        raise ValueError(
            f"framework corpus ({len(files)} files) exceeds the greenfield offer cap ({cap}); "
            "refusing to silently truncate. Check for unexpected files under the framework "
            "paths (e.g. gitignored clutter in a non-git hub, or a misconfigured root) — ADR-0025."
        )
    if not files:
        warnings.warn(
            "framework corpus resolved to 0 files — the hub may be misconfigured or git "
            "enumeration returned nothing; no value would be offered (ADR-0025).",
            stacklevel=2,
        )

    # R3: surface framework work that will NOT propagate until committed (commit-before-apply).
    untracked = list_untracked_framework_files(root)
    if untracked:
        listed = "\n  ".join(untracked)
        warnings.warn(
            f"{len(untracked)} untracked file(s) under framework paths will NOT propagate via "
            f"/apply-framework until committed (ADR-0025):\n  {listed}",
            stacklevel=2,
        )

    return files


def compute_greenfield_package(
    template_root: Path | str,
    target_path: Path | str,
    offer_set: list[str],
) -> ChangePackage:
    """Classify an offer set against a target with **no** framework lineage (the APPLY route, R4).

    The greenfield sibling of :func:`compute_package`: it builds an :class:`OnDiskBaseline` (no
    drift scan, no manifest) and runs the **same** floor primitive (:func:`_classify`). Because the
    baseline reports no provable divergence and no policy, every existing target file at a
    framework path classifies as ``value-unverified`` (the floor — flagged, never overwritten) and
    every path the target lacks as ``inert``. Returns the identical :class:`ChangePackage` shape as
    the UPDATE route, so the report front-end and ``stage_branch`` consume it unchanged.

    .. warning::
        This is an **ASSESS-phase** read only. It computes classifications; it does **not** enforce
        consent. The R8 APPLY assent preflight (a human-authored ``primary_human`` + the
        deploy-step-zero stub, see :mod:`scripts.distribute.repo_safety_check`) is a **required
        precondition** of any caller that then stages this package — never route this result to
        ``stage_branch`` outside the gated DEPLOY path.

    Args:
        template_root: Hub (template) repository root.
        target_path: Target repository root (need not be a git repo or framework-tracked).
        offer_set: Relative, forward-slash paths to offer (typically :func:`greenfield_offer_set`).

    Returns:
        A :class:`ChangePackage` describing each offered file's classification.
    """
    hub_root = Path(template_root).resolve()
    target_root = Path(target_path).resolve()
    baseline = OnDiskBaseline()
    items = [
        _classify(
            rel.replace("\\", "/"),
            hub_root=hub_root,
            target_root=target_root,
            baseline=baseline,
        )
        for rel in offer_set
    ]
    return ChangePackage(target_path=str(target_root), items=items)


def package_report(package: ChangePackage) -> str:
    """Render a human-readable, content-free summary of a change package.

    Args:
        package: The computed change package.

    Returns:
        A markdown summary suitable for ``--dry-run`` output.
    """
    counts = package.counts()
    lines = [
        f"# Change Package — {package.target_path}",
        "",
        f"**Stageable**: {len(package.stageable)} "
        f"({len(package.requires_interpretation)} flagged for review)  ·  "
        f"**Pinned-dropped**: {len(package.pinned_dropped)}  ·  "
        f"**Diverged (assess)**: {len(package.diverged)}  ·  "
        f"**Excluded**: {len(package.excluded)}",
        "",
        "| Classification | Count |",
        "|----------------|-------|",
    ]
    lines.extend(f"| {name} | {count} |" for name, count in sorted(counts.items()))
    lines.append("")
    if package.has_unmediable_candidates():
        route_note = "FULL ROOM — collision-diverged candidates present"
    elif package.needs_interpretation():
        route_note = "FAST-PATH — single referee interprets flagged (value-unverified) overwrites"
    else:
        route_note = "FAST-PATH — obviously inert (no overwrites, no divergence)"
    lines.append(f"Assessment route: {route_note}")
    return "\n".join(lines)


@dataclass(frozen=True)
class RouteDecision:
    """An escalate-only routing override for one ``value-unverified`` file (R4).

    Records the agent's interpretation verdict and the resulting effective route *alongside* the
    machine classification — the :class:`ChangeItem` classification is never mutated, so both the
    deterministic machine verdict and the judgment override survive (Principle #1) and there
    is no temporal coupling in ``stageable`` / ``diverged`` / ``counts``.

    Attributes:
        file_path: Relative, forward-slash path of the file.
        machine_classification: The classification produced by :func:`_classify`.
        agent_verdict: The interpretation room's verdict for this file.
        effective_route: The route after applying :func:`reclassify_route`.
        reason: Short justification for the (non-)escalation.
    """

    file_path: str
    machine_classification: str
    agent_verdict: str
    effective_route: str
    reason: str


def reclassify_route(machine_classification: str, agent_verdict: str, triage_hint: str) -> str:
    """Map an interpretation verdict to an effective route — escalate-only (R4).

    Pure function (no I/O) so routing is unit-testable independently of the agent that produces the
    verdict. It only ever *increases* scrutiny: a ``value-unverified`` file may be escalated to
    ``collision-diverged`` (held back from staging / routed toward UNMEDIABLE); it is never demoted
    to a silent safe update. A disagreement between the deterministic triage hint (``behavioral``)
    and a benign agent verdict is itself an escalation — this defends the floor against a
    prompt-injected "this is cosmetic" verdict reaching the routing decision (the agent verdict can
    never lower scrutiny below the mechanical floor).

    Args:
        machine_classification: The classification from :func:`_classify`.
        agent_verdict: The room's verdict (e.g. "cosmetic", "behavioral-blast-radius",
            "likely-deliberate").
        triage_hint: The deterministic triage hint ("cosmetic" / "behavioral" / "unknown").

    Returns:
        ``"collision-diverged"`` when escalated, otherwise ``machine_classification`` unchanged.
    """
    # Only the floor's value-unverified class is subject to the bridge; every other route is final.
    if machine_classification != "value-unverified":
        return machine_classification
    verdict = (agent_verdict or "").strip().lower()
    # triage_hint MUST be the deterministic R2 output (assessment.triage_diff), never agent-derived
    # content — normalize defensively so a stray case/space cannot suppress the behavioral co-gate.
    hint = (triage_hint or "").strip().lower()
    # Deterministic-hint / agent disagreement: the mechanical triage says behavioral but the agent
    # (possibly influenced by injected content) calls it benign → escalate; distrust the verdict.
    if hint == "behavioral" and verdict in BENIGN_VERDICTS:
        return "collision-diverged"
    if verdict in ESCALATING_VERDICTS:
        return "collision-diverged"
    return machine_classification


def main() -> None:
    """CLI entry point — print a change-package report for a target."""
    parser = argparse.ArgumentParser(description="Compute a distribution change package")
    parser.add_argument("template_root", help="Hub (template) repository root")
    parser.add_argument("target", help="Target repository root")
    parser.add_argument("--offer", nargs="+", required=True, help="Relative paths to offer")
    args = parser.parse_args()

    package = compute_package(args.template_root, args.target, args.offer)
    print(package_report(package))


if __name__ == "__main__":
    main()
