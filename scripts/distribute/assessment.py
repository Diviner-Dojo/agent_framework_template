"""Interpreted-assessment layer for ``/distribute`` (the mechanical, testable half).

The mechanical safety floor (:mod:`scripts.distribute.change_package`) flags every overwrite it
cannot prove safe as ``value-unverified``. This module turns those flagged files into the *content*
the advisory assessment doc needs — deterministically, so the consent-critical parts (which files
are surfaced, the directing-attention disclaimer, secret scrubbing, ordering) are unit-testable and
never depend on an agent. The agent's four-question interpretation is layered on top as input data
(:class:`Interpretation`); it *explains* the flagged files, it does not decide whether to flag them
(the floor already did, by construction).

Boundaries (security review of SPEC-20260523-100224):

- Diffs are computed with stdlib :mod:`difflib` — never a subprocess ``git diff`` with
  target-controlled paths.
- Diff text is target-internal content. It belongs ONLY in the target-local assessment doc; it must
  never reach an ntfy payload or a hub ``write_event`` (those carry counts / routes / labels only).
- Diff lines are scrubbed against the hub's canonical secret patterns before they enter the written
  doc (the staging commit uses ``--no-verify``, bypassing the target's own secret scanner).
"""

from __future__ import annotations

import difflib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scripts.distribute.change_package import ChangePackage

# Reuse the hub's canonical 12 secret patterns (single source of truth) — the pre-commit hook's
# ``SECRET_PATTERNS``. The hook module is import-safe: all runtime logic is under ``main()`` /
# ``__main__``, so importing it only binds the constant + pure helpers.
_HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / ".claude" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))
try:
    from validate_tool_use import SECRET_PATTERNS  # type: ignore  # noqa: E402

    _SECRET_PATTERNS_LOADED = True
except Exception:  # pragma: no cover - defensive; import succeeds against the hub's own hooks
    SECRET_PATTERNS = []
    _SECRET_PATTERNS_LOADED = False

# An empty pattern list (e.g. a hook refactor) scrubs nothing — treat it the same as a failed
# import and fail closed (security review F1), so redact_secrets raises rather than silently no-op.
if not SECRET_PATTERNS:
    _SECRET_PATTERNS_LOADED = False

REDACTION = "[REDACTED — potential secret]"

ADVISORY_HEADER = (
    "> **ADVISORY / target-overridable.** This assessment was produced by the hub during "
    "/distribute. It has **no authority** over this project. The target's developer is free to "
    "reject, partially accept, edit, or override any conclusion here. Nothing in this branch is "
    "merged or pushed."
)

DIRECTING_ATTENTION = (
    "This section directs your attention; it does not certify safety. These overwrites ride "
    "on the target's mutable baseline, which can mislabel a deliberate customization as a "
    "safe update (finding B1). Read the flagged files before merging."
)

# Consent-stakes ordering: behavioral first, then unknown, then cosmetic. ALL value-unverified
# files appear regardless — a cosmetic-triaged file is never dropped, only sorted lower (R5).
_STAKES_ORDER = {"behavioral": 0, "unknown": 1, "cosmetic": 2}

_COMMENT_PREFIXES: dict[str, tuple[str, ...]] = {
    ".py": ("#",),
    ".sh": ("#",),
    ".yaml": ("#",),
    ".yml": ("#",),
    ".toml": ("#",),
    ".cfg": ("#",),
    ".js": ("//",),
    ".ts": ("//",),
}

_VERSION_NUM = re.compile(r"\bv?\d+\.\d+(?:\.\d+)?\b")
_COMPARISON_OPS = ("==", ">=", "<=", "!=", "<", ">", "(", ")", "if ", "return ", "and ", "or ")


@dataclass
class OverwriteDiff:
    """Per-file diff + deterministic triage for one ``value-unverified`` overwrite (R2).

    A SIBLING to ``ChangeItem`` (deliberately kept off ``ChangeItem`` so the classifier and its
    ``counts()`` / ``package_report`` stay content-free — confidentiality is structural, not
    disciplinary).

    Attributes:
        file_path: Relative, forward-slash path.
        diff_text: UNREDACTED hub-vs-target unified diff — used for triage/interpretation. Callers
            MUST scrub via :func:`redact_secrets` before writing it into the assessment doc, and
            MUST NOT put it in any ntfy / ``write_event`` payload.
        triage_hint: ``"cosmetic"`` / ``"behavioral"`` / ``"unknown"`` (safe default ``unknown``).
            INVARIANT (independent-perspective D): this MUST be the deterministic R2 output of
            :func:`triage_diff` — it is the *sole* provenance for the escalate-only co-gate in
            :func:`scripts.distribute.change_package.reclassify_route`. Never populate it from
            agent-supplied content, or a prompt-injected "this is cosmetic" could suppress the
            behavioral co-gate and lower scrutiny below the mechanical floor.
    """

    file_path: str
    diff_text: str
    triage_hint: str


@dataclass
class Interpretation:
    """The room's four-question judgment for one overwrite — agent-supplied input to the doc.

    The agent produces these; :func:`build_assessment_doc` only formats them. It never decides
    whether a file is surfaced (the floor does).

    Attributes:
        file_path: Relative, forward-slash path.
        meaningful: Answer to Q1 (cosmetic vs behavioral, free text).
        backflow: Q2 — is the target's version possibly the better one (route up, don't resolve)?
        blast_radius: Q3 — would taking the hub's version break the target's other code (honest).
        confidence: Q4 — calibrated confidence in [0, 1].
        verdict: One of cosmetic / benign / behavioral-blast-radius / likely-deliberate.
    """

    file_path: str
    meaningful: str
    backflow: bool
    blast_radius: str
    confidence: float
    verdict: str


def redact_secrets(text: str) -> str:
    """Replace any line containing a known secret with a redaction marker (R8).

    Reuses the hub's canonical secret patterns. Operates line-by-line so one secret does not blank
    a whole diff. Triage/interpretation run on the UNREDACTED text; only the text written into the
    assessment doc is scrubbed (the staging commit bypasses the target's own scanner).

    Args:
        text: Diff (or any) text destined for the written assessment doc.

    Returns:
        The text with secret-bearing lines replaced by :data:`REDACTION`.
    """
    if not _SECRET_PATTERNS_LOADED:
        raise RuntimeError(
            "Secret patterns unavailable (hook import failed) — refusing to write an unscrubbed "
            "diff into the assessment doc (staging uses --no-verify). Fail closed."
        )
    if not text:
        return text
    out: list[str] = []
    for line in text.splitlines():
        if any(pat.search(line) for _name, pat in SECRET_PATTERNS):
            out.append(REDACTION)
        else:
            out.append(line)
    return "\n".join(out)


def _is_comment_line(stripped: str, file_path: str) -> bool:
    """Whether a stripped payload line is a line-comment for the file's language."""
    ext = Path(file_path).suffix.lower()
    prefixes = _COMMENT_PREFIXES.get(ext)
    if prefixes is None:
        return False
    return any(stripped.startswith(p) for p in prefixes)


def _is_version_string_line(stripped: str) -> bool:
    """Whether a line's only semantic content is a dotted version number (e.g. ``v = "3.5.0"``).

    Excludes lines that also contain comparison/logic operators (e.g. ``if V >= "3.5":``), which
    are behavioral even though they contain a version.
    """
    if not _VERSION_NUM.search(stripped):
        return False
    if any(op in stripped for op in _COMPARISON_OPS):
        return False
    remainder = _VERSION_NUM.sub("", stripped)
    return bool(re.fullmatch(r"""[\w\s.=:"'`,\-]*""", remainder))


def triage_diff(diff_text: str | None, file_path: str) -> str:
    """Deterministically triage a unified diff as ``cosmetic`` / ``behavioral`` / ``unknown`` (R2).

    Safe default is ``unknown`` — a false-positive ``cosmetic`` costs a clobber, a false-negative
    costs one extra agent question. Most-severe wins across hunks (``behavioral`` > ``unknown`` >
    ``cosmetic``). Python-significant whitespace is never ``cosmetic`` (indentation is semantic); a
    version string in a ``.py`` file is ``behavioral`` (it may gate a code path).

    Args:
        diff_text: The unified diff, or ``None``/empty.
        file_path: The file's relative path (drives language-specific rules).

    Returns:
        ``"cosmetic"`` / ``"behavioral"`` / ``"unknown"``.
    """
    if not diff_text or "Binary files" in diff_text:
        return "unknown"
    is_py = file_path.endswith(".py")
    changed = [
        ln
        for ln in diff_text.splitlines()
        if ln[:1] in ("+", "-") and not ln.startswith(("+++", "---"))
    ]
    if not changed:
        return "unknown"

    saw_behavioral = saw_unknown = saw_cosmetic = False
    for raw in changed:
        stripped = raw[1:].strip()
        if stripped == "":
            # Pure whitespace/blank-line change: semantic in Python, cosmetic elsewhere.
            if is_py:
                saw_unknown = True
            else:
                saw_cosmetic = True
        elif _is_comment_line(stripped, file_path):
            saw_cosmetic = True
        elif _is_version_string_line(stripped):
            if is_py:
                saw_behavioral = True
            else:
                saw_cosmetic = True
        else:
            saw_behavioral = True

    if saw_behavioral:
        return "behavioral"
    if saw_unknown:
        return "unknown"
    if saw_cosmetic:
        return "cosmetic"
    return "unknown"


def _read_text(path: Path) -> str:
    """Read a file as UTF-8 text; binary/unreadable yields ``""`` (triage → unknown)."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def compute_overwrite_diffs(
    package: ChangePackage, hub_root: Path | str, target_root: Path | str
) -> list[OverwriteDiff]:
    """Compute the hub-vs-target diff + triage hint for each ``value-unverified`` overwrite (R2).

    Uses stdlib :func:`difflib.unified_diff` (no subprocess). One entry per
    ``package.requires_interpretation`` file. ``diff_text`` is UNREDACTED (triage runs on the true
    diff); the caller scrubs via :func:`redact_secrets` before writing to the doc.

    Args:
        package: The computed change package.
        hub_root: Hub (template) repository root.
        target_root: Target repository root.

    Returns:
        One :class:`OverwriteDiff` per flagged overwrite (orientation: target → hub, so ``+`` lines
        are what the hub's update would introduce).
    """
    hub = Path(hub_root)
    target = Path(target_root)
    results: list[OverwriteDiff] = []
    for item in package.requires_interpretation:
        rel = item.file_path
        hub_text = _read_text(hub / rel)
        tgt_text = _read_text(target / rel)
        diff = "".join(
            difflib.unified_diff(
                tgt_text.splitlines(keepends=True),
                hub_text.splitlines(keepends=True),
                fromfile=f"target/{rel}",
                tofile=f"hub/{rel}",
            )
        )
        results.append(OverwriteDiff(rel, diff, triage_diff(diff, rel)))
    return results


def _stakes_key(od: OverwriteDiff) -> tuple[int, str]:
    """Sort key for consent-stakes ordering (behavioral first, cosmetic last; all included)."""
    return (_STAKES_ORDER.get(od.triage_hint, 1), od.file_path)


def build_assessment_doc(
    package: ChangePackage,
    overwrite_diffs: list[OverwriteDiff],
    interpretations: list[Interpretation],
    *,
    room_summary: str = "",
) -> str:
    """Assemble the advisory assessment doc deterministically (R5/R6/R7).

    The consent-critical structure — advisory header, the *counted* directing-attention disclaimer,
    consent-stakes ordering, scrubbed diffs, and the honest backflow section — is built here so it
    is unit-testable and independent of the agent. Only the interpretation *content* is agent-
    supplied. No raw target content leaves this doc (the caller writes it to the target branch
    only; counts/routes/labels are the only things that may go to ntfy / ``write_event``).

    Args:
        package: The change package (for content-free counts).
        overwrite_diffs: Per-file diffs + triage for the ``value-unverified`` overwrites.
        interpretations: The room's per-file judgments (matched to diffs by ``file_path``).
        room_summary: Optional room verdict prose (no target file bodies).

    Returns:
        The full markdown assessment-doc body.
    """
    interp_by_path = {i.file_path: i for i in interpretations}
    n = len(overwrite_diffs)
    lines = [ADVISORY_HEADER, ""]

    if n:
        lines += [
            f"> **{n} file(s) in this update could not be proven safe against a hub ancestor "
            f"(finding B1). They are staged but flagged — read these {n} before merging.** "
            f"{DIRECTING_ATTENTION}",
            "",
        ]

    counts = package.counts()
    lines += ["## Change package", "", "| Classification | Count |", "|---|---|"]
    lines += [f"| {name} | {count} |" for name, count in sorted(counts.items())]
    lines.append("")

    lines += ["## Files that would overwrite target content", ""]
    if not overwrite_diffs:
        lines += ["_None — no overwriting files in this update._", ""]
    for od in sorted(overwrite_diffs, key=_stakes_key):
        interp = interp_by_path.get(od.file_path)
        lines += [f"### {od.file_path}", "", f"- **Triage**: {od.triage_hint}"]
        if interp is not None:
            lines += [
                f"- **Meaningful?** {interp.meaningful}",
                f"- **Blast radius?** {interp.blast_radius}",
                f"- **Confidence**: {interp.confidence:.2f}",
                f"- **Verdict**: {interp.verdict}",
            ]
        else:
            lines.append("- _Interpretation pending — treat as needs-review._")
        lines += ["", "```diff", redact_secrets(od.diff_text).rstrip("\n"), "```", ""]

    backflow = [i for i in interpretations if i.backflow]
    lines += ["## Backflow candidates", ""]
    if backflow:
        lines.append(
            "_The target's version of these files differs and **may be better OR may be stale** — "
            "we cannot tell without a hub-side ancestor. If genuinely better, route it UP via "
            "`/analyze-project` + the adoption log; `/distribute` does not propagate upward._"
        )
        lines += [f"- `{i.file_path}`" for i in backflow]
    else:
        lines.append("_None flagged._")
    lines.append("")

    if room_summary:
        # Label agent-supplied prose so it reads distinctly from mechanical sections — a crafted
        # diff can't lower routing (escalate-only) but could taint this free text (security F2).
        lines += [
            "## Room verdict _(agent-supplied — not mechanically verified)_",
            "",
            room_summary,
            "",
        ]

    return "\n".join(lines)
