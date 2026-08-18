"""Guards the constitution against silent count/citation drift.

Why this file exists
--------------------
Before ADR-0031 the repo carried a three-way disagreement that nothing detected:
``CLAUDE.md`` listed **nine** numbered principles, ``PHILOSOPHY.md`` asserted
**eight** in three places, and ADR-0031 Decision 6 ratified **seven**. The drift
was live and undetected for months, which is proof that these strings rot
silently. This module is the detector.

What a green run here actually means — in plain words
------------------------------------------------------
Read this paragraph before trusting the word "passed". It is the honest,
non-technical statement of how far this guard reaches, written because a
reviewer found the previous version of this explanation unexplainable without
notes — and a mechanism the developer cannot explain is a defect in the
mechanism, not in the developer.

Green means all five of these, and nothing more:

1. **The constitution still has the shape it is supposed to have.** Seven
   principles, numbered 1 to 7 with no gaps, and each slot still about the
   subject it was ratified to be about.
2. **Nobody anywhere on the live instruction surface says a different number of
   principles**, and no live file except ``CLAUDE.md`` keeps its own rival copy
   of the list.
3. **No live file points at a principle number that does not exist** (a "#8"
   after #8 was retired), and — for every sentence whose *wording* this module
   recognises — no live file points at the wrong existing number.
4. **Where ``CLAUDE.md`` or ``PHILOSOPHY.md`` says "this rule is written down in
   file X", file X really does contain that rule.**
5. **Where a live file points at something specific as the enforcement — a
   second copy of a safety block, or a named test — that thing is still there
   and still says the same words.** The panel-size block in ``/review`` must
   match the skill's byte for byte, and every pytest node id quoted in
   instruction prose must resolve to a test that exists.

Green does **not** mean the constitution is correct, wise, or complete. Three
specific gaps are worth naming out loud:

* **The wording filter (point 3).** This module only inspects a sentence for a
  wrong principle number if the sentence uses a phrase the module already knows
  — the phrases live in ``CONCEPT_KEYWORDS``. A wrong citation phrased in words
  nobody has taught it goes straight through. Measured on the current tree, the
  filter reaches **86.6% of the citation lines it is allowed to look at**
  (58 of 67); ``test_concept_binding_coverage_has_not_regressed`` prints that
  number on every run and fails below 85%, so the reach is a measured quantity
  rather than a claim in a comment.
* **The debt registers.** Some files are known to be wrong and are not fixable
  from the slice that added this module. They are listed in
  ``KNOWN_STALE_CITATIONS`` / ``KNOWN_STALE_COUNTS`` with an owner. An entry
  does **not** hand the file a blank cheque: each one records *how many* bad
  lines that file currently has, and a new bad line pushes the count over the
  registered number and fails. What an entry does buy is silence about the
  specific number of pre-existing problems already counted.
* **Untracked files.** The scan reads ``git ls-files``, so a brand-new file that
  has never been ``git add``-ed is invisible to every check here.

What this module actually guarantees (and what it does not)
-----------------------------------------------------------
The same thing again, in the module's own vocabulary. The guard has five
independent layers and each catches a different failure; none catches
everything.

1. **Shape of the list** — ``CLAUDE.md`` has exactly the ratified number of
   numbered principles, contiguously numbered from 1, with each slot's identity
   pinned by a distinguishing phrase from ADR-0031 Decision 6. Catches: a
   principle added, dropped, renumbered, or two slots swapping identity.
2. **Count strings** — no prose *anywhere on the live instruction surface* says
   a number of principles that disagrees with the list, and no live file other
   than ``CLAUDE.md`` carries its own competing numbered principle list.
   Catches: exactly the three-way drift above.

   This layer was originally scoped to ``CLAUDE.md`` / ``PHILOSOPHY.md`` only,
   while layer 3 already scanned the whole live surface. That asymmetry was a
   real hole, not a simplification: ``docs/diviner-dojo-framework-presentation.html``
   published "9 Non-Negotiable Principles" from inside ``LIVE_FILES`` and the
   suite reported green, and ``FRAMEWORK.md`` carried a whole *competing*
   eight-item constitution including both retired principles (that file was
   retired outright on 2026-08-17 — ADR-0036). The scan now
   iterates :func:`live_instruction_files`, exempting only the paths in
   ``KNOWN_STALE_COUNTS``.

   ``KNOWN_STALE_COUNTS`` is deliberately a **separate register** from
   ``KNOWN_STALE_CITATIONS``. Sharing one register would let a citation
   exemption silently confer a count exemption on the same file — and the two
   debts have different owners (citations are re-pointed per file; counts are
   fixed by the ``syncing-framework-docs`` doc-sync pass).
3. **Citations** — two distinct checks over the live instruction surface:

   a. *Out-of-range* — no live file cites ``Principle #N`` where ``N`` exceeds
      the list length (or is < 1). Catches a citation of a **retired** principle
      (#8, #9).
   b. *Concept-bound* — for a line that names a concept in
      ``CONCEPT_KEYWORDS`` **and** cites a principle number, the cited number
      must be the slot whose title carries that concept. Catches a citation that
      is **wrong but still in range** — e.g. education cited as ``#6`` when
      education is now ``#5`` and ``#6`` is curated-memory approval. This is the
      failure the stakes describe: two live files citing different numbers for
      the same mechanism.

   **The limit of (b):** it only sees lines whose wording matches a keyword in
   ``CONCEPT_KEYWORDS``. A wrong-but-in-range citation phrased in words no
   keyword covers passes silently. The keyword lists are drawn from how this
   corpus actually phrases each concept; extend them when a new phrasing
   appears. A green run means "no *detected* mismatch", not "no mismatch" —
   and ``test_concept_binding_coverage_has_not_regressed`` measures and prints
   how big the detected fraction is (86.6% of citation lines today) so the
   caveat carries a number instead of a shrug.

   The remaining unreachable lines are printed by name on every run, so the gap
   is a list rather than an adjective. There are **nine**, spread across six
   files: ``.claude/commands/quiz.md``, ``.claude/commands/review.md``,
   ``.claude/hooks/validate_tool_use.py`` (three),
   ``scripts/distribute/change_package.py``, ``scripts/goal_loop.py`` and
   ``scripts/verify_paths_not_taken.py`` (two). The denominator moved from 63 to 67
   on 2026-08-17 when ``scripts/goal_loop.py`` left ``KNOWN_STALE_CITATIONS`` (its
   one wrong citation was fixed), which put its four citation lines back under
   measurement -- an exemption suppresses the file's lines from the coverage
   fraction too, so draining the register lowers the percentage while strictly
   improving the tree. One of them cites ``#7`` for the
   ``.claude/settings.json`` permission surface being "developer-applied only",
   which reads like the human-approval principle (#6) under the merged
   numbering — but the intent is genuinely ambiguous, that file belongs to
   another slice in flight, and a keyword forcing a number there would
   manufacture a false positive as easily as a catch. It is reported to that
   slice's owner rather than guessed at.

4. **Governance location claims** — when ``CLAUDE.md`` or ``PHILOSOPHY.md``
   says a mechanism is "specified in"/"stated in"/"lives in" some file, that
   file must actually contain the mechanism. Catches *inert prose that reads as
   a mechanism*: the constitution asserting a safety guarantee has a home, and
   the home being empty. The motivating instance is real — all three
   constitutional sentences about review plurality claimed it was "specified in
   ``/review``" while ``.claude/commands/review.md`` contained zero occurrences
   of the word. See ``GOVERNANCE_MECHANISMS``.
5. **Pointed-at enforcement** — layer 4 checks that a named file contains the
   mechanism; this layer checks that what it contains has not drifted, and that
   prose naming a *test* names a real one. Two checks:
   ``TestPluralityLanded::test_every_restatement_of_the_block_is_verbatim``
   (``/review``'s copy of the panel-size block is byte-identical to the skill's,
   and ``/review`` still carries it) and
   ``TestProseReferencesResolve::test_cited_pytest_node_ids_exist`` (every
   ``tests/…py::Class::test_name`` quoted on the live surface resolves). Catches
   the half-life of layer 4: the home stays named and non-empty while the two
   copies of a safety number silently diverge, or the enforcing test is renamed
   and the sentence naming it becomes decorative. Node ids are resolved against
   ``tests/`` **on disk**, not ``git ls-files``, so a slice that adds a test
   module and cites it in the same change resolves against its own new file.

Scope of the scan, and why each hole is where it is
---------------------------------------------------
``scripts/`` **is in scope.** Merged Principle #2 reads "Capture is automatic.
Enforced by scripts and hooks, not by instruction" — the constitution names
``scripts/`` as its enforcement layer, so the constitution's own guard has to
look there. Excluding it hid five citations of retired #8 in shipped Python.

Deliberately out of scope, each for a stated reason:

* ``docs/adr/`` — ADRs are immutable (Principle #4). Rewriting one to match a
  later constitution would falsify the record.
* ``discussions/``, ``memory/``, ``docs/reviews/``, ``docs/sprints/`` and the
  other dated-artifact families — same argument: records of what was true when
  written.
* ``BUILD_STATUS.md`` — session-scoped working state whose principle citations
  are quotes of decisions made under the numbering in force at the time.
* ``FRAMEWORK_CHANGELOG.md`` — a dated changelog; its entries describe past
  releases under past numbering.
* ``tests/`` — this module's own prose would otherwise be scanned by itself.

Design rules for this module
----------------------------
1. **Read, never hardcode.** The expected count, the principle titles, and every
   concept-to-number binding are parsed out of ``CLAUDE.md``. If the developer
   ratifies an eighth principle, these tests follow automatically instead of
   turning into a second, stale copy of the constitution.
2. **Scan git-tracked files only.** ``git ls-files`` excludes ``__pycache__``,
   build junk, and — importantly — ``.claude/worktrees/``, which holds vendored
   third-party repos that are none of this framework's business.
3. **Every allowlist entry is a debt with an owner and a target number**, and
   ``test_known_stale_allowlist_does_not_rot`` fails when an entry's file no
   longer violates, so the allowlist cannot outlive the debt it records.
"""

from __future__ import annotations

import ast
import difflib
import re
import subprocess
from pathlib import Path
from typing import NamedTuple

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Scope: which files carry live instructions vs. historical record
# ---------------------------------------------------------------------------

# Directories whose contents are dated records of past reasoning. Rewriting them
# to match a later constitution would falsify the record, so they are out of
# scope. docs/adr is excluded by Principle #4 (ADRs are never deleted or
# rewritten); the rest are the same argument applied to reviews, specs,
# handoffs, research notes and one-off analyses.
HISTORICAL_DIR_PREFIXES = (
    "docs/adr/",
    "docs/reviews/",
    "docs/sprints/",
    "docs/research/",
    "docs/analysis/",
    "docs/handoff/",
    "docs/proposals/",
    "docs/samples/",
    "docs/plans/",
    "discussions/",
    "memory/",
    "brainstorms/",
    "diagnostics/",
    ".claude/worktrees/",
)

# Dated-ID filename prefixes (the conventions in CLAUDE.md > Conventions, plus
# the derived artifact families). A file named this way is a record even when it
# sits outside the directories above.
HISTORICAL_BASENAME_PREFIXES = (
    "ADR-",
    "REV-",
    "SPEC-",
    "DISC-",
    "REFL-",
    "ANALYSIS-",
    "SYNTHESIS-",
    "PROPOSAL-",
    "PROMPT-",
    "META-REVIEW-",
    "HANDOFF-",
    "WALKTHROUGH-",
    "WORKITEMS-",
    "comparison-",
)

# The live instruction surface this module polices.
#   .claude/        — the whole agent-facing instruction layer
#   docs/education/ — the education-gate registry and its cross-repo contract
#   scripts/        — the enforcement layer merged Principle #2 names by hand;
#                     a citation in shipped Python is as live as one in a rule
LIVE_DIR_PREFIXES = (
    ".claude/",
    "docs/education/",
    "scripts/",
)

# Live reference documents that sit outside those directories. BUILD_STATUS.md
# and FRAMEWORK_CHANGELOG.md are deliberately absent — see the module docstring.
LIVE_FILES = (
    "CLAUDE.md",
    "PHILOSOPHY.md",
    # FRAMEWORK.md removed 2026-08-17: the file itself was retired (ADR-0036), so there
    # is nothing left to keep live. CLAUDE.md is the constitution; PHILOSOPHY.md is the why.
    "README.md",
    "docs/FRAMEWORK_SPECIFICATION.md",
    "docs/STEWARD_ARCHITECTURE.md",
    "docs/how-to-use-presentation.html",
    "docs/diviner-dojo-framework-presentation.html",
)

TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".py", ".html", ".json", ".sh", ".txt"}


# Files that still carry stale citations and are NOT editable from the slice that
# introduced this test — they belong to other work in flight in the same
# checkout, or sit outside the constitutional file scope entirely.
#
# This is a debt register, not a licence and not an exhaustive statement of the
# reconciliation's follow-up scope. Each value names the wrong number, the
# correct target under ADR-0031 Decision 6, and who owns the fix. Delete the
# entry when the file is re-pointed: `test_known_stale_allowlist_does_not_rot`
# fails both when a listed path disappears and when a listed path stops
# violating, so an entry cannot quietly become permanent cover.
#
# The register is COUNT-SCOPED, not file-scoped. An earlier version exempted a
# listed path's entire contents from both citation checks, so a brand-new bad
# citation added to any of these 23 files was invisible until the entry drained.
# Each entry now records how many violations of each kind the file has *today*;
# the checks tolerate exactly that many and fail on the next one, and
# `test_known_stale_allowlist_does_not_rot` fails if the real number moves in
# either direction — down (debt paid, tighten or delete the entry) or up (a new
# violation, which the check above will already have failed on).
#
# Regenerate the numbers after any legitimate change with:
#   pytest tests/test_constitution_consistency.py::TestCitationNumbering -q
# and read them off the failure message, which prints the measured pair.
class StaleCitations(NamedTuple):
    """How many known-bad citations a registered file currently carries."""

    out_of_range: int
    wrong_concept: int
    reason: str


KNOWN_STALE_CITATIONS: dict[str, StaleCitations] = {
    # The counts are what the DETECTOR currently sees, which is deliberately not
    # the same as the human debt described in the reason string: a reason may name
    # three wrong citations while only one is machine-visible, because the other two
    # are phrased in words CONCEPT_KEYWORDS does not cover. Trust the reason for what
    # to fix; trust the numbers for what the guard is currently blind to.
    #
    # --- Owned by the /review + commands slice of the same reconciliation -----
    ".claude/commands/batch-evaluate.md": StaleCitations(
        0,
        1,
        "L114 cites #7 for 'human decides'; human approval is now #6. Commands slice.",
    ),
    ".claude/commands/deliberate.md": StaleCitations(
        0,
        1,
        "L17 cites #4 for the independence principle; independence is now #3. Commands slice.",
    ),
    ".claude/commands/meta-review.md": StaleCitations(
        0,
        1,
        "cites #7 for 'human decides' (no automatic relaxation); human approval is now #6. "
        "Commands slice.",
    ),
    ".claude/commands/onboard.md": StaleCitations(
        0,
        1,
        "L11 cites #5 for 'superseded but retained'; ADR supersession is now #4. Commands slice.",
    ),
    ".claude/commands/retro.md": StaleCitations(
        0,
        1,
        "L240 cites #7 for 'human decides' (no automatic relaxation); human approval is now #6. "
        "Commands slice.",
    ),
    # --- Live rules/docs outside the constitutional file scope ----------------
    ".claude/rules/testing_requirements.md": StaleCitations(
        0,
        1,
        "L61 cites #4 for 'human-enforced at /review'; independent review is now #3. "
        "Path-scoped rules are outside the constitution slice's file list.",
    ),
    "docs/education/CONTRACTS.md": StaleCitations(
        0,
        1,
        "L330 cites #7 for human-promoted curated memory; human approval is now #6. "
        "Cross-repo versioned contract — re-point with a contract revision, not in passing.",
    ),
    "docs/education/gates.yaml": StaleCitations(
        0,
        1,
        "L3 cites #6 for the walkthrough/quiz/explain-back gate; education is now #5. "
        "Education-registry scope.",
    ),
    "docs/FRAMEWORK_SPECIFICATION.md": StaleCitations(
        0,
        2,
        "Re-measured 2026-08-17. The out-of-range hit is GONE: L1332 used to read 'was "
        "CLAUDE.md Principle #8 until v3.6' -- a historical reference the detector could not "
        "distinguish from a live citation -- and now reads 'Principle 8 under the old "
        "numbering', which says the same thing without minting a citation. That removed an "
        "exemption this reconciliation had itself created. The two remaining wrong_concept "
        "hits are DETECTOR FALSE POSITIVES, kept registered so the guard keeps watching the "
        "file: L576 and L1262 each name TWO concepts on one line -- 'education walkthrough'/"
        "'education gates' AND builder-is-never-its-own-judge -- so CONCEPT_KEYWORDS matches "
        "the education slot (#5) while the line correctly cites #3 for independence. Same "
        "false-positive class as the path-not-taken checker specimens; /retro item, do not "
        "'fix' the prose to appease it.",
    ),
    # FRAMEWORK.md: entry RETIRED 2026-08-17. The debt was paid by DELETION, not by
    # re-pointing: the file published a complete competing eight-principle constitution
    # and is gone (ADR-0036). One constitution (CLAUDE.md), one philosophy
    # (PHILOSOPHY.md). Deleted rather than left registered, per
    # test_known_stale_allowlist_does_not_rot, which fails on a path that no longer exists.
    "README.md": StaleCitations(
        0,
        1,
        "L106 cites #4 for mid-build independence; independence is now #3. Doc-sync scope.",
    ),
    # --- Shipped Python. Constitution slice must not edit scripts/. -----------
    "scripts/audit_calibration.py": StaleCitations(
        0,
        1,
        "L11 cites #7 for the human-mediated promotion gate; human approval is now #6.",
    ),
    "scripts/education/__init__.py": StaleCitations(
        0,
        1,
        "L4 cites #6 for walkthrough/quiz/explain-back gates; education is now #5.",
    ),
    "scripts/education/gate_registry.py": StaleCitations(
        0,
        1,
        "L3 cites #6 for walkthrough/quiz/explain-back gates; education is now #5.",
    ),
    # scripts/goal_loop.py: entry RETIRED 2026-08-17. L1360 cited #4 for builder!=checker
    # inside the loop while .claude/commands/goal-loop.md:74 and the orchestrating-goal-loops
    # skill both already said #3 -- two halves of one feature disagreeing about which
    # principle it implements. The driver now cites #3. Deleted rather than left registered,
    # per test_known_stale_allowlist_does_not_rot.
    # scripts/quality_gate.py: entry RETIRED 2026-08-07. The --rebaseline paragraph
    # it described was rewritten by the guard-prose reconciliation (the flag no longer
    # writes the baseline at all) and now cites #6, the human-approval principle, as
    # this entry's reason line prescribed. Deleted rather than left registered,
    # per test_known_stale_allowlist_does_not_rot.
}

# Files on the live surface that still state a WRONG NUMBER OF PRINCIPLES, or carry
# their own competing numbered principle list. Kept separate from
# KNOWN_STALE_CITATIONS on purpose: a file may cite principle numbers correctly and
# still publish the wrong count (and vice versa), the two debts have different
# owners, and merging the registers would let one exemption silently confer the
# other. docs/diviner-dojo-framework-presentation.html is the proof — it was in
# LIVE_FILES, in no register at all, and published "9 Non-Negotiable Principles"
# while the suite reported green.
#
# Every entry is a debt with a target: the merged count is SEVEN (ADR-0031
# Decision 6). `test_known_stale_counts_allowlist_does_not_rot` fails when an
# entry's file no longer violates, so the register drains instead of becoming
# permanent cover. It drained on 2026-08-17: docs/STEWARD_ARCHITECTURE.md and both
# presentation decks were corrected to seven and their entries deleted. The two that
# remain are not doc-sync debt — one is intentional history, the other is blocked on
# an open governance decision. Each says which.
KNOWN_STALE_COUNTS: dict[str, str] = {
    # FRAMEWORK.md: entry RETIRED 2026-08-17 together with the file. Governance question
    # B2 was decided by the developer — delete it and rewire `/seed` to inline the seven
    # (ADR-0036) — so the competing eight-principle list is gone rather than exempted.
    # Note for the record: an earlier version of this entry excused the file as "NOT in
    # FRAMEWORK_PATHS so it does not propagate". That was measured FALSE on 2026-08-17 —
    # `/apply-framework` is one channel of three, and the file travelled on the other two
    # (published on `upstream/main`, and copied into every project by `seed.md`). The
    # review panel named that contradiction the "clean tell"; it is preserved here because
    # the reasoning is the artifact, not the exemption.
    "docs/FRAMEWORK_SPECIFICATION.md": (
        "Two remaining hits, both INTENTIONAL HISTORY rather than doc-sync debt, so this "
        "entry is not expected to drain: L94 'the constitution went from nine principles to "
        "seven' is the sentence that *records* the merge, and L1604 is the v3.5 changelog "
        "row describing what v3.5 shipped ('Prime Objective above the eight principles'). "
        "Rewriting either to satisfy the regex would falsify the record it exists to keep "
        "(Principle #4 in spirit: superseded, never rewritten). The live count claims in "
        "this file were corrected to seven on 2026-08-17."
    ),
}


def _tracked_files() -> list[str]:
    """Return every git-tracked path, POSIX-separated, relative to the repo root."""
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [p for p in result.stdout.split("\0") if p]


def _is_historical(rel_path: str) -> bool:
    """True when the path is a dated record rather than a live instruction."""
    if rel_path.startswith(HISTORICAL_DIR_PREFIXES):
        return True
    return Path(rel_path).name.startswith(HISTORICAL_BASENAME_PREFIXES)


def live_instruction_files() -> list[str]:
    """Git-tracked files that carry live instructions bound to the current numbering."""
    out = []
    for rel in _tracked_files():
        if Path(rel).suffix.lower() not in TEXT_SUFFIXES:
            continue
        if _is_historical(rel):
            continue
        if rel in LIVE_FILES or rel.startswith(LIVE_DIR_PREFIXES):
            out.append(rel)
    return sorted(out)


# ---------------------------------------------------------------------------
# Parsing the constitution out of CLAUDE.md
# ---------------------------------------------------------------------------

_PRINCIPLE_LINE = re.compile(r"^(\d+)\.\s+\*\*(?P<title>.+?)\*\*")

# A "## Non-Negotiable Principles" heading at any level, and any markdown heading.
# Used to detect a *competing* constitution in a live file other than CLAUDE.md.
_PRINCIPLES_HEADING = re.compile(r"^(#{1,6})\s+.*Non-Negotiable Principles\s*$", re.IGNORECASE)
_ANY_HEADING = re.compile(r"^(#{1,6})\s")

# Matches "Principle #4", "Principles #1/#2", "Principle #6, #7". Captures the
# whole run so every number in it can be checked, not just the first.
_CITATION = re.compile(r"[Pp]rinciples?\s*#\d+(?:\s*[/,&]\s*#\d+)*")
_CITED_NUMBER = re.compile(r"#(\d+)")

# Any spelled-out or digit count immediately qualifying the word "principle(s)"
# or "commitment(s)". PHILOSOPHY.md restates the list as "the seven technical
# commitments"; that phrasing rots exactly like "the eight principles" did.
_COUNT_STRING = re.compile(
    r"\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)[\s-]+"
    r"(?:(?:non-negotiable\s+)?principles?|technical\s+commitments?)\b",
    re.IGNORECASE,
)

# Spelled-out numbers in the paragraph between the Non-Negotiable Principles
# heading and its first numbered item. CLAUDE.md opens that section with
# "There are **seven**." — a count string the regex above cannot see because the
# word "principles" is not adjacent to it.
_SPELLED_NUMBER = re.compile(
    r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\b", re.IGNORECASE
)

_WORD_TO_INT = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}

# Concept -> principle binding.
#
# The key is a *substring of the principle's title in CLAUDE.md*, never an
# integer: the slot number is resolved by reading CLAUDE.md, so a future
# renumber moves every binding at once. The values are the phrases this corpus
# actually uses to name that concept; a line containing one of them AND a
# principle citation must cite that slot.
#
# Keep keywords specific enough that they name the mechanism, not merely mention
# a related word — "capture" alone matches prose like "Capture findings as ..."
# and would produce false failures, so the capture entry uses full phrases.
# Every keyword below was measured against the live surface before being added:
# it must match at least one real citation line and produce zero false failures
# on the clean tree. Keywords that match nothing are dead weight that inflates
# apparent coverage, and `test_every_concept_keyword_matches_something` now fails
# on one. Two were removed for exactly that reason -- "independent evaluator" and
# "non-participating specialist", both measured at 0 occurrences across the whole
# live surface.
#
# One near-miss is worth recording, because acting on it would have broken a
# check rather than fixed one: a review reported "reward function" (spaced) as a
# third dead keyword. It is not. It appears 3 times on the live surface, one of
# them scripts/quality_gate.py:30, whose whole KNOWN_STALE_CITATIONS entry exists
# because of it -- deleting the spaced form silently drained that debt entry and
# turned the register green on an unfixed file. Both spellings are kept.
#
# "builder != checker" is the single deliberate exception: 0 occurrences today,
# retained because it is the ASCII spelling of "builder ≠ checker" (1 occurrence,
# so the glyph form is live), and a future author who types the ASCII form should
# not slip through. It is listed in that test's `allowed_dead`.
CONCEPT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Reasoning is the primary artifact": (
        "reasoning is the primary artifact",
        "reasoning artifact",
        "decision lineage is preserved",
        "the understanding is the asset",
    ),
    "generator is never the sole evaluator": (
        "independent evaluation",
        "independently evaluated",
        "independent checker",
        "independence",
        "sole evaluator",
        "sole judge",
        "builder ≠ checker",
        "builder != checker",  # ASCII spelling of the above; future-proofing
        "distinct agent id",
        "differs from the builder",
        "separate context",
        # the safety-critical-test rule in the testing rules: the /review gate
        # is what supplies the independent context
        "human-enforced at `/review`",
    ),
    "Understanding before merge": (
        "walkthrough",
        "explain-back",
        "education gate",
        "understood it well enough to teach",
        "deferred gate",
        "re-deferred",
    ),
    "Curated memory needs human approval": (
        "human approval",
        "human gate",
        "human decides",
        "human-promoted",
        "auto-promoted",
        "automatic removal",
        "automatic relaxation",
        "human-mediated",
        "developer-approved",
        "developer approval",
        "explicit human approval",
        # BOTH spellings are load-bearing and both were measured. The corpus
        # uses them in different files: scripts/quality_gate.py:30 writes
        # "part of the reward function" (space) and CLAUDE.md:47 writes
        # "reward-function surface" (hyphen). Shipping only the spaced form left
        # the CLAUDE.md line unchecked, which is where a wrong number in the
        # constitution itself would have hidden; dropping the spaced form
        # instead silently drains the scripts/quality_gate.py debt entry.
        "reward function",
        "reward-function",
    ),
    "ADRs are never deleted": (
        "never deleted",
        "not deleted",
        "superseded",
        "the decision is documented",
    ),
    "Capture is automatic": (
        "capture is automatic",
        "capture must be automatic",
        "capture cannot be skipped",
        "uncaptured",
        "skip capture",
        "capture each tick",
    ),
    "Clarify before acting": (
        "design fork",
        "genuine fork",
        "95% rule",
        "before acting",
        "stop and ask",
    ),
}

# Minimum fraction of citation lines on the non-exempt live surface that the
# concept-binding check is able to inspect at all. Measured at 91.7% when this
# floor was set (33 of 36 lines). The floor exists so the guard's own reach is
# an asserted number rather than a sentence in a docstring: adding citation
# lines in wordings nobody has taught the module silently thins the check, and
# this is what notices.
MIN_CONCEPT_COVERAGE = 0.85


def parse_principles(claude_md: str) -> list[tuple[int, str]]:
    """Extract ``(number, title)`` for each entry of the Non-Negotiable Principles list."""
    lines = claude_md.splitlines()
    try:
        start = next(
            i for i, line in enumerate(lines) if line.strip() == "## Non-Negotiable Principles"
        )
    except StopIteration:  # pragma: no cover - guarded by its own test below
        pytest.fail("CLAUDE.md has no '## Non-Negotiable Principles' heading")

    found: list[tuple[int, str]] = []
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        match = _PRINCIPLE_LINE.match(line)
        if match:
            found.append((int(match.group(1)), match.group("title")))
    return found


def principles_section_preamble(claude_md: str) -> str:
    """The prose between the Non-Negotiable Principles heading and its first item."""
    lines = claude_md.splitlines()
    start = next(
        i for i, line in enumerate(lines) if line.strip() == "## Non-Negotiable Principles"
    )
    preamble: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("## ") or _PRINCIPLE_LINE.match(line):
            break
        preamble.append(line)
    return "\n".join(preamble)


def wrong_count_hits(text: str, expected: int) -> list[str]:
    """``"line N: 'eight principles'"`` for every count string that disagrees with ``expected``."""
    hits: list[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for match in _COUNT_STRING.finditer(line):
            token = match.group(1).lower()
            value = _WORD_TO_INT.get(token) or int(token)
            if value != expected:
                hits.append(f"line {line_no}: {match.group(0)!r}")
    return hits


def enumerated_principle_lists(text: str) -> list[str]:
    """``"line N: 8 numbered items"`` for each self-contained numbered principle list.

    A *competing constitution* is worse than a stale count string: it restates the
    principles in full under old numbering, so a reader who lands on it never learns
    a merge happened. ``FRAMEWORK.md`` carried one (the retired eight, including both
    principles ADR-0031 Decision 6 retired) until it was deleted on 2026-08-17
    (ADR-0036). Only ``CLAUDE.md`` may hold this list. The check stays: it is what
    makes a *reintroduced* second constitution fail loudly instead of drifting.

    Heading match is level-agnostic (``#`` .. ``######``) so demoting the heading does
    not evade the check; the section ends at the next heading of the same or shallower
    level. Two or more numbered items are required, so a passing *reference* to the
    principles never trips it.
    """
    lines = text.splitlines()
    found: list[str] = []
    for index, line in enumerate(lines):
        heading = _PRINCIPLES_HEADING.match(line.strip())
        if not heading:
            continue
        depth = len(heading.group(1))
        count = 0
        for following in lines[index + 1 :]:
            deeper = _ANY_HEADING.match(following)
            if deeper and len(deeper.group(1)) <= depth:
                break
            if _PRINCIPLE_LINE.match(following):
                count += 1
        if count >= 2:
            found.append(f"line {index + 1}: {count} numbered items under {line.strip()!r}")
    return found


def resolve_concept_slots(principles: list[tuple[int, str]]) -> dict[str, int]:
    """Map each ``CONCEPT_KEYWORDS`` title-substring to the principle number carrying it.

    Resolved from the parsed CLAUDE.md list, never hardcoded: the whole point is
    that a renumber re-points every concept binding automatically.
    """
    slots: dict[str, int] = {}
    for title_substring in CONCEPT_KEYWORDS:
        matches = [n for n, title in principles if title_substring.lower() in title.lower()]
        assert len(matches) == 1, (
            f"concept key {title_substring!r} matches {len(matches)} principle titles "
            f"({matches}); it must identify exactly one slot. Update CONCEPT_KEYWORDS "
            "to match the ratified titles."
        )
        slots[title_substring] = matches[0]
    return slots


def _cited_numbers(line: str) -> set[int]:
    """Every principle number cited anywhere on ``line``."""
    return {
        int(n) for citation in _CITATION.finditer(line) for n in _CITED_NUMBER.findall(citation[0])
    }


def out_of_range_hits(text: str, highest: int) -> list[str]:
    """``"line N: 'Principle #8'"`` for every citation of a principle that does not exist."""
    hits: list[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for citation in _CITATION.finditer(line):
            bad = [
                int(n)
                for n in _CITED_NUMBER.findall(citation.group(0))
                if int(n) > highest or int(n) < 1
            ]
            if bad:
                hits.append(f"line {line_no}: {citation.group(0)!r}")
    return hits


def wrong_concept_hits(text: str, concept_slots: dict[str, int]) -> list[str]:
    """Citations that are in range but point at the wrong principle for a named concept."""
    hits: list[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        cited = _cited_numbers(line)
        if not cited:
            continue
        lowered = line.lower()
        for title_substring, keywords in CONCEPT_KEYWORDS.items():
            matched = [k for k in keywords if k in lowered]
            if not matched:
                continue
            expected = concept_slots[title_substring]
            if expected not in cited:
                hits.append(
                    f"line {line_no}: names {matched} "
                    f"(principle #{expected}, {title_substring!r}) but cites {sorted(cited)}"
                )
    return hits


def concept_binding_coverage(concept_slots: dict[str, int]) -> tuple[int, int, list[str]]:
    """``(bound, total, unbound_descriptions)`` over citation lines the checks may inspect.

    "Bound" means the line's wording matches at least one ``CONCEPT_KEYWORDS``
    phrase, so the wrong-but-in-range check can form an opinion about it. An
    unbound line carries a principle number that nothing verifies.
    """
    bound = 0
    total = 0
    unbound: list[str] = []
    for rel in live_instruction_files():
        if rel in KNOWN_STALE_CITATIONS:
            continue
        text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if not _cited_numbers(line):
                continue
            total += 1
            lowered = line.lower()
            if any(k in lowered for kws in CONCEPT_KEYWORDS.values() for k in kws):
                bound += 1
            else:
                unbound.append(f"{rel}:{line_no}: {line.strip()[:110]}")
    return bound, total, unbound


# ---------------------------------------------------------------------------
# Governance location claims: "this rule is specified in X" must be true of X
# ---------------------------------------------------------------------------
#
# The failure this catches has a name in the repo's own review vocabulary:
# *inert prose that reads as a mechanism*. The constitution asserts that a
# safety guarantee has a concrete home; the home is empty; the guarantee exists
# only as a sentence about itself. It is the assert-don't-measure defect applied
# to the location of a safety mechanism, and it shipped once already — CLAUDE.md
# and PHILOSOPHY.md both said review plurality was "specified in `/review`" while
# `.claude/commands/review.md` contained zero occurrences of "plurality".
#
# The check is deliberately general rather than a hardcoded assertion about
# plurality: it reads the *claim* out of the constitution, resolves whatever
# file the claim names, and verifies the mechanism is there. Register a new
# mechanism below and every future sentence that claims a home for it is checked
# for free.


class GovernanceMechanism(NamedTuple):
    """A governance rule the constitution claims lives in a specific file."""

    name: str
    #: The claim block must mention the mechanism (lowercased substrings, any).
    claim_markers: tuple[str, ...]
    #: Every one of these must appear (lowercased) in each file the claim names.
    required_markers: tuple[str, ...]


GOVERNANCE_MECHANISMS: tuple[GovernanceMechanism, ...] = (
    GovernanceMechanism(
        name="review plurality (panel-size floors)",
        claim_markers=("plurality",),
        required_markers=(
            "panel size",
            "at least 3 independent specialists",
            "at least 2",
        ),
    ),
)

#: Files whose governance claims are binding. These two are the constitution.
CLAIMING_FILES: tuple[str, ...] = ("CLAUDE.md", "PHILOSOPHY.md")

# --- Review plurality: the one normative home, and where the numbers came from
#
# Panel size is the only governance mechanism in this repo that is a bare
# integer, which makes it uniquely easy to restate somewhere else and uniquely
# easy to get wrong there. The numbers are pinned here (like the principle count
# is pinned at seven) so that lowering a floor requires editing an assertion,
# and the drift check compares every other restatement against the skill.
#
# PROVENANCE, stated exactly. ADR-0031 Decision 6 ratified that plurality is
# retained as a *dispatch* concern and that "the panel size for critical-risk
# changes lives in `/review` and the `selecting-review-gates` skill". It does
# NOT state a number: grepping the ADR for a numeric floor returns nothing, and
# neither does ADR-0032. The integers below were chosen by the slice that landed
# the mechanism, not ratified by an ADR, and saying otherwise here would be the
# same unmeasured-citation defect this module exists to catch. They are pinned
# so that changing one is a visible edit to an assertion rather than a quiet
# edit to prose -- which is what makes raising or lowering a floor reviewable.
PLURALITY_SKILL = ".claude/skills/selecting-review-gates/SKILL.md"

#: Minimum independent specialists per risk tier. See PROVENANCE above: these
#: are implementation-chosen numbers under ADR-0031 Decision 6's disposition,
#: not numbers the ADR itself states.
PLURALITY_FLOORS: dict[str, int] = {"critical": 3, "high": 2, "medium": 1, "low": 1}

# "Critical risk: at least 3 independent specialists", "High risk: at least 2.",
# "Medium / Low risk: 1 is sufficient." and the un-colonned prose restatement
# CLAUDE.md's Rules Index uses ("critical risk at least 3 independent specialists").
_FLOOR_STATEMENT = re.compile(
    r"\b(critical|high|medium|low)(?:\s*/\s*(critical|high|medium|low))?\s+risk[:,]?\s+"
    r"(?:at least\s+)?(\d+)\b",
    re.IGNORECASE,
)


def _restated_floors(text: str) -> list[tuple[str, int]]:
    """``(tier, count)`` for every panel-size floor a file states."""
    found: list[tuple[str, int]] = []
    for match in _FLOOR_STATEMENT.finditer(text):
        number = int(match.group(3))
        for tier in (match.group(1), match.group(2)):
            if tier:
                found.append((tier.lower(), number))
    return found


def plurality_floors() -> dict[str, int]:
    """Parse the panel-size floors out of the skill that owns them."""
    text = (REPO_ROOT / PLURALITY_SKILL).read_text(encoding="utf-8")
    return dict(_restated_floors(text))


# --- The block, not merely its numbers --------------------------------------
#
# ``PLURALITY_SKILL`` asserts in prose that ``/review`` "carries a byte-identical
# copy of the block above". Nothing measured that. ``_restated_floors`` compares
# tier->number pairs only, so a restatement could keep "at least 3" and drop the
# sentence defining what *independent* means ("each dispatched in a separate
# context, none of which sees another's findings"), and the skill's claim would
# quietly become false while every test stayed green. That is the same
# assert-don't-measure shape as a governance location claim, one level finer.
#
# The canonical span is the heading through the end of the rationale sentence.
# What follows it legitimately differs between the two files -- the skill
# continues into its tier table, the command into Step 5 -- so the span is
# anchored at both ends rather than run to the next heading.
PLURALITY_BLOCK_HEADING = "### Panel size — review plurality"
PLURALITY_BLOCK_END = "does not govern review panels."

#: The command that actually dispatches the panel. The skill names it by hand,
#: so its copy is required, not merely checked-if-present.
PLURALITY_DISPATCH_COMMAND = ".claude/commands/review.md"


def plurality_block(text: str) -> str | None:
    """The canonical panel-size block, or ``None`` if the file does not carry it."""
    start = text.find(PLURALITY_BLOCK_HEADING)
    if start == -1:
        return None
    end = text.find(PLURALITY_BLOCK_END, start)
    if end == -1:
        return None
    return text[start : end + len(PLURALITY_BLOCK_END)].strip()


def plurality_restaters() -> list[str]:
    """Live instruction files other than the skill that carry the panel-size heading."""
    found: list[str] = []
    for rel in live_instruction_files():
        if rel == PLURALITY_SKILL:
            continue
        text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
        if PLURALITY_BLOCK_HEADING in text:
            found.append(rel)
    return found


# Phrases that turn a mention into a *location claim*. Only backticked
# references appearing after one of these — and before the clause ends — are
# treated as "the constitution says the mechanism is here". A mention with no
# location phrase ("plurality matters") claims nothing and is not checked.
_LOCATION_PHRASE = re.compile(
    r"\b(?:specified in|stated in|defined in|documented in|written down in|"
    r"normative home is|lives? in)\b",
    re.IGNORECASE,
)

# A location clause ends at a semicolon, a sentence-ending period, or a spaced
# em/double dash. Backticked spans are masked out before this is applied, so a
# path's own dots and dashes cannot end the clause early.
_CLAUSE_END = re.compile(r";|\.\s|\.$|\s—\s|\s--\s")

_BACKTICKED = re.compile(r"`([^`]+)`")

# A markdown line that starts a new logical block: heading, list item, or
# numbered item. Used to split wrapped prose into claim-sized units so a claim
# split across two source lines is still seen whole, without gluing a whole
# bullet list into one block.
_BLOCK_START = re.compile(r"^\s*(?:#{1,6}\s|[-*+]\s|\d+\.\s|\|)")


def claim_blocks(text: str) -> list[tuple[int, str]]:
    """Split markdown into ``(first_line_number, single-line text)`` logical blocks.

    A block is a paragraph, a heading, a table row, or one list item including
    its wrapped continuation lines. Whitespace is normalised to single spaces so
    a claim that wraps across source lines reads as one sentence.
    """
    blocks: list[tuple[int, list[str]]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            blocks.append((line_no, []))  # hard break
            continue
        if not blocks or not blocks[-1][1] or _BLOCK_START.match(line):
            blocks.append((line_no, [line.strip()]))
        else:
            blocks[-1][1].append(line.strip())
    return [(n, " ".join(parts)) for n, parts in blocks if parts]


def location_claim_targets(block: str) -> list[str]:
    """Backticked references introduced by a location phrase in ``block``."""
    spans = [(m.start(), m.end(), m.group(1)) for m in _BACKTICKED.finditer(block)]
    masked = list(block)
    for start, end, _ in spans:
        for i in range(start, end):
            masked[i] = "\0"
    masked_text = "".join(masked)

    targets: list[str] = []
    for phrase in _LOCATION_PHRASE.finditer(masked_text):
        clause_start = phrase.end()
        end_match = _CLAUSE_END.search(masked_text, clause_start)
        clause_end = end_match.start() if end_match else len(masked_text)
        for start, end, token in spans:
            if clause_start <= start and end <= clause_end:
                targets.append(token)
    return targets


def resolve_reference(token: str) -> str | None:
    """Resolve a backticked reference to a repo-relative path, or ``None``.

    Handles the three shapes the constitution actually uses: a literal path
    (``.claude/skills/x/SKILL.md``), a slash command (``/review`` ->
    ``.claude/commands/review.md``), and a bare skill name (``selecting-review-gates``
    -> ``.claude/skills/selecting-review-gates/SKILL.md``).
    """
    token = token.strip()
    candidates: list[str] = []
    if token.startswith("/"):
        candidates.append(f".claude/commands/{token[1:]}.md")
    else:
        candidates.append(token)
        candidates.append(f".claude/skills/{token}/SKILL.md")
        candidates.append(f".claude/commands/{token}.md")
    for candidate in candidates:
        if (REPO_ROOT / candidate).is_file():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Prose that points at a test
# ---------------------------------------------------------------------------
#
# A governance location claim one level down. Live instruction files name pytest
# node ids as the thing that enforces a rule -- the panel-size block's own
# explanation in `selecting-review-gates`, the `severity-calibration` skill, and
# CLAUDE.md's Known Limitations all do it. (No tally is written here; the count
# changes whenever a citation is added, and a stale number in a comment is the
# defect this module exists to catch.) A node id is a string: rename the test and
# the prose still reads like a working guard while naming nothing. Same failure
# family as "specified in `/review`" when `/review` was empty, so it gets the
# same treatment: resolve the reference, or fail.
#
# Two shapes appear in the corpus: the full form with a path, and the bare
# `Class::test_name` form used for a second reference to a file already named.

#: ``tests/foo.py::Class::test_name`` -- path plus one or more ``::`` segments.
_FULL_NODE_ID = re.compile(r"(tests/[\w./-]+\.py)((?:::[A-Za-z_]\w*)+)")

#: Bare ``TestClass::test_name``. Anchored to the pytest naming convention on
#: both halves so ordinary prose containing ``::`` cannot match.
_BARE_NODE_ID = re.compile(r"(?<![\w/.])(Test[A-Za-z_]\w*)::(test_\w+)")


def node_id_index() -> dict[str, set[str]]:
    """Map each test module to the symbols a node id may name in it.

    Values contain top-level ``test_*`` function names, ``Test*`` class names,
    and ``Class::method`` pairs.

    Built by walking ``tests/`` on disk rather than :func:`_tracked_files`, on
    purpose: a slice that *adds* a test module and cites it in the same change
    would otherwise fail against its own new file, because ``git ls-files`` does
    not see it until it is staged. Resolution targets are read from the working
    tree; only the *scan* for references is restricted to tracked files.
    """
    index: dict[str, set[str]] = {}
    for path in sorted((REPO_ROOT / "tests").rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:  # pragma: no cover - a broken test file fails elsewhere
            continue
        names: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                names.add(node.name)
            elif isinstance(node, ast.ClassDef):
                names.add(node.name)
                for member in node.body:
                    if isinstance(member, ast.FunctionDef | ast.AsyncFunctionDef):
                        names.add(f"{node.name}::{member.name}")
        index[rel] = names
    return index


def unresolved_node_ids(index: dict[str, set[str]]) -> list[str]:
    """Every pytest node id cited on the live surface that names nothing real."""
    broken: list[str] = []
    every_symbol = {symbol for symbols in index.values() for symbol in symbols}
    for rel in live_instruction_files():
        text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
        for match in _FULL_NODE_ID.finditer(text):
            module, tail = match.group(1), match.group(2).lstrip(":")
            if module not in index:
                broken.append(f"{rel} cites {match.group(0)} -- no such test module")
            elif tail not in index[module]:
                broken.append(f"{rel} cites {match.group(0)} -- {module} has no {tail!r}")
        for match in _BARE_NODE_ID.finditer(text):
            symbol = f"{match.group(1)}::{match.group(2)}"
            if symbol not in every_symbol:
                broken.append(f"{rel} cites {symbol} -- no test module defines it")
    return broken


@pytest.fixture(scope="module")
def claude_md_text() -> str:
    return (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def philosophy_text() -> str:
    return (REPO_ROOT / "PHILOSOPHY.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def principles(claude_md_text: str) -> list[tuple[int, str]]:
    return parse_principles(claude_md_text)


@pytest.fixture(scope="module")
def concept_slots(principles: list[tuple[int, str]]) -> dict[str, int]:
    return resolve_concept_slots(principles)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPrincipleList:
    """CLAUDE.md's numbered list is the single source of truth."""

    def test_exactly_seven_principles(self, principles: list[tuple[int, str]]) -> None:
        """ADR-0031 Decision 6 ratified seven. Nine (main) and six (v4) are both wrong."""
        assert len(principles) == 7, (
            f"CLAUDE.md lists {len(principles)} numbered principles, expected 7 "
            f"(ADR-0031 Decision 6). Found: {[t for _, t in principles]}. "
            "If the developer has ratified a different count, update ADR-0031's "
            "successor ADR and this assertion together — never this assertion alone."
        )

    def test_numbering_is_contiguous_from_one(self, principles: list[tuple[int, str]]) -> None:
        """A gap or duplicate here is how a citation silently starts meaning two things."""
        numbers = [n for n, _ in principles]
        assert numbers == list(range(1, len(numbers) + 1)), (
            f"CLAUDE.md principle numbering is {numbers}; expected 1..{len(numbers)} with no "
            "gaps or repeats."
        )

    def test_ratified_titles_are_present(self, principles: list[tuple[int, str]]) -> None:
        """Pin the identity of each slot so a renumber cannot quietly swap two principles.

        These are the distinguishing phrases from ADR-0031 Decision 6's table, not
        the full text — the full wording lives in CLAUDE.md and may be edited for
        clarity without breaking this guard.
        """
        expected_markers = {
            1: "Reasoning is the primary artifact",
            2: "Capture is automatic",
            3: "generator is never the sole evaluator",
            4: "ADRs are never deleted",
            5: "Understanding before merge",
            6: "Curated memory needs human approval",
            7: "Clarify before acting",
        }
        actual = dict(principles)
        for number, marker in expected_markers.items():
            assert number in actual, f"CLAUDE.md has no principle #{number}"
            assert marker.lower() in actual[number].lower(), (
                f"Principle #{number} is '{actual[number]}', expected it to be the one "
                f"about '{marker}' (ADR-0031 Decision 6). A slot swapped identity — every "
                "citation of this number across the fleet now points somewhere else."
            )

    def test_retired_principles_are_not_silently_dropped(self, claude_md_text: str) -> None:
        """The two retirements must stay traceable, or stale citations become unresolvable.

        A reader holding a derived project's older artifact that cites '#8' needs
        CLAUDE.md to tell them where the value went. ADR-0031 Decision 6 relocated
        both; deleting the note would make the relocation invisible.
        """
        assert "Retired, and where the value went" in claude_md_text, (
            "CLAUDE.md must keep the retirement note explaining where retired main #3 "
            "(plurality) and #8 (least-complex intervention) went."
        )
        assert "plurality" in claude_md_text.lower(), (
            "Retired main #3's plurality half is explicitly NOT retired (ADR-0031 "
            "Decision 6) and must remain named in CLAUDE.md."
        )


class TestCountStrings:
    """The three-way drift ADR-0031 found lived entirely in prose count strings."""

    @pytest.mark.regression
    def test_no_stale_count_string_in_live_files(self, principles: list[tuple[int, str]]) -> None:
        """PHILOSOPHY.md said 'eight' against a nine-item CLAUDE.md for months.

        Regression guard: any spelled-out or numeric count qualifying the word
        'principle(s)' anywhere on the live instruction surface must equal the number
        of principles actually listed in CLAUDE.md.

        Scoped to the whole live surface, not just the two constitutional documents.
        The narrow version of this check reported green while
        ``docs/diviner-dojo-framework-presentation.html`` — a member of ``LIVE_FILES``,
        exempted by no register — published "9 Non-Negotiable Principles". CLAUDE.md
        and PHILOSOPHY.md are both in ``LIVE_FILES``, so nothing is lost by widening.
        """
        expected = len(principles)
        violations: dict[str, list[str]] = {}
        for rel in live_instruction_files():
            hits = wrong_count_hits(
                (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace"), expected
            )
            if hits:
                violations[rel] = hits

        unexpected = {p: h for p, h in violations.items() if p not in KNOWN_STALE_COUNTS}
        assert not unexpected, (
            f"CLAUDE.md lists {expected} principles, but these live files disagree "
            f"(this exact drift is what ADR-0031 Decision 6 was written to end): {unexpected}. "
            "Fix the count, or add a KNOWN_STALE_COUNTS entry naming the owner of the fix."
        )

    @pytest.mark.regression
    def test_only_claude_md_carries_a_numbered_principle_list(self) -> None:
        """A second enumerated constitution is the count drift in its most durable form.

        ``FRAMEWORK.md`` restated all eight pre-merge principles verbatim, including
        the two ADR-0031 Decision 6 retired. A reader who landed there was not merely
        told the wrong number — they were handed the wrong constitution, with no signal
        that a merge happened. That file was retired on 2026-08-17 (ADR-0036), which is
        the fix; this test is the guard that keeps it fixed. Only CLAUDE.md may hold the
        enumerated list, so a future second constitution fails here on the day it lands.
        """
        violations: dict[str, list[str]] = {}
        for rel in live_instruction_files():
            if rel == "CLAUDE.md":
                continue
            hits = enumerated_principle_lists(
                (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
            )
            if hits:
                violations[rel] = hits

        unexpected = {p: h for p, h in violations.items() if p not in KNOWN_STALE_COUNTS}
        assert not unexpected, (
            f"live files other than CLAUDE.md carry their own numbered principle list: "
            f"{unexpected}. Replace the copy with a pointer to CLAUDE.md — a duplicated "
            "constitution drifts the moment the real one is amended."
        )

    def test_known_stale_counts_allowlist_does_not_rot(
        self, principles: list[tuple[int, str]]
    ) -> None:
        """A KNOWN_STALE_COUNTS entry must name a file that exists AND still violates.

        Mirrors ``test_known_stale_allowlist_does_not_rot`` for the count register.
        Without the second half a doc-synced file keeps a permanent exemption, and the
        next wrong count in it is invisible — which is precisely how the presentation
        HTML went undetected.
        """
        missing = [p for p in KNOWN_STALE_COUNTS if not (REPO_ROOT / p).exists()]
        assert not missing, (
            f"KNOWN_STALE_COUNTS names paths that no longer exist: {missing}. Delete the entries."
        )

        expected = len(principles)
        clean: list[str] = []
        for rel in KNOWN_STALE_COUNTS:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
            still_violating = bool(wrong_count_hits(text, expected)) or (
                rel != "CLAUDE.md" and bool(enumerated_principle_lists(text))
            )
            if not still_violating:
                clean.append(rel)

        assert not clean, (
            f"KNOWN_STALE_COUNTS still exempts files with no wrong count and no competing "
            f"principle list: {clean}. The doc-sync debt was paid — delete these entries so "
            "the files are guarded again."
        )

    def test_count_and_citation_registers_stay_separate(self) -> None:
        """The two debt registers must not be collapsed into one.

        A citation exemption must never confer a count exemption. Both registers
        legitimately name some of the same paths, so this guards the *code* shape —
        that two distinct names exist and neither aliases the other — rather than
        their contents.

        This test also used to assert that at least one path was exempted for its
        count but NOT for its citations, naming the presentation deck as the
        motivating case. That assertion contradicted the paragraph above: it was a
        claim about contents, in a test that says it does not check contents. It
        also inverted the incentive. On 2026-08-17 both deck headers,
        ``docs/STEWARD_ARCHITECTURE.md`` and the spec's live count claims were
        corrected to seven and the drained entries deleted (as
        ``test_known_stale_counts_allowlist_does_not_rot`` requires) — and *paying
        the debt off* turned this test red, because the two registers that remained
        legitimately named the same two files. A guard that fails when the debt it
        tracks is cleared is a guard that rewards leaving it there. The shape checks
        below hold whether the registers overlap fully, partially, or not at all.
        """
        assert KNOWN_STALE_COUNTS is not KNOWN_STALE_CITATIONS, (
            "KNOWN_STALE_COUNTS must be its own register; aliasing it to "
            "KNOWN_STALE_CITATIONS would let a citation exemption silently exempt a "
            "wrong principle count in the same file."
        )
        # The registers carry different value types, so collapsing them cannot happen
        # quietly: counts map path -> reason string, citations map path ->
        # StaleCitations(out_of_range, wrong_concept, reason). If a future edit points
        # one name at the other, one of these two assertions fails.
        assert all(isinstance(v, str) for v in KNOWN_STALE_COUNTS.values()), (
            "KNOWN_STALE_COUNTS must map path -> reason string. A StaleCitations value "
            "here means the citation register was assigned to this name."
        )
        assert all(isinstance(v, StaleCitations) for v in KNOWN_STALE_CITATIONS.values()), (
            "KNOWN_STALE_CITATIONS must map path -> StaleCitations. A bare string here "
            "means the count register was assigned to this name."
        )

    def test_section_preamble_states_the_right_count(
        self, claude_md_text: str, principles: list[tuple[int, str]]
    ) -> None:
        """CLAUDE.md's own headline count ("There are **seven**.") must match its list.

        The count-string regex cannot see this one — the number is not adjacent to
        the word "principles" — and it is the first thing a reader of the
        constitution sees.
        """
        preamble = principles_section_preamble(claude_md_text)
        spelled = {m.group(1).lower() for m in _SPELLED_NUMBER.finditer(preamble)}
        wrong = sorted(w for w in spelled if _WORD_TO_INT[w] != len(principles))
        assert not wrong, (
            f"the Non-Negotiable Principles preamble says {wrong} but the list has "
            f"{len(principles)} entries. Preamble text: {preamble.strip()!r}"
        )


class TestCitationNumbering:
    """No live instruction may cite a principle number that resolves to the wrong thing."""

    def test_scan_covers_the_files_that_matter(self) -> None:
        """Guard the guard: a scope bug would make every other test here vacuous."""
        scanned = set(live_instruction_files())
        must_include = {
            "CLAUDE.md",
            "PHILOSOPHY.md",
            ".claude/rules/autonomous_workflow.md",
            ".claude/rules/testing_requirements.md",
            ".claude/agents/facilitator.md",
            ".claude/agents/steward.md",
            ".claude/skills/selecting-review-gates/SKILL.md",
            ".claude/commands/review.md",
            "docs/education/gates.yaml",
            # scripts/ is the enforcement layer merged Principle #2 names; five
            # citations of retired #8 hid there while it was out of scope.
            "scripts/quality_gate.py",
            "scripts/goal_loop.py",
            "scripts/telemetry/dashboard.py",
        }
        missing = sorted(must_include - scanned)
        assert not missing, f"live-instruction scan missed known live files: {missing}"
        assert not any(p.startswith("docs/adr/") for p in scanned), (
            "ADRs are immutable history and must not be in scope"
        )
        assert not any(p.startswith("discussions/") for p in scanned), (
            "Layer 1 discussions are sealed and must not be in scope"
        )

    @pytest.mark.regression
    def test_no_live_file_cites_a_principle_above_the_list_length(
        self, principles: list[tuple[int, str]]
    ) -> None:
        """ADR-0031 itself shipped a citation pointing at a principle it retired.

        Regression guard against exactly that: a live instruction citing #8 or #9
        after the merge resolves to nothing, and a derived project inherits the
        false citation.
        """
        highest = len(principles)
        unexpected: dict[str, list[str]] = {}
        for rel in live_instruction_files():
            text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
            hits = out_of_range_hits(text, highest)
            entry = KNOWN_STALE_CITATIONS.get(rel)
            allowed = entry.out_of_range if entry else 0
            if len(hits) > allowed:
                unexpected[rel] = [f"{len(hits)} hits, {allowed} registered", *hits]

        assert not unexpected, (
            f"live instruction files cite a principle number above #{highest} more often "
            f"than their KNOWN_STALE_CITATIONS entry allows: {unexpected}. "
            "Re-point the citation to the merged numbering in ADR-0031 Decision 6 "
            "(old #4->#3, #5->#4, #6->#5, #7->#6, #9->#7; old #3 and #8 are retired). "
            "A registered file is exempt only up to the number of violations recorded "
            "when the entry was written — never for its whole contents."
        )

    @pytest.mark.regression
    def test_no_live_file_cites_a_wrong_number_for_a_named_concept(
        self, concept_slots: dict[str, int]
    ) -> None:
        """The wrong-but-in-range citation — the failure the >length check cannot see.

        Regression guard for the merge's central hazard: a principle number
        re-pointed in one file and missed in another, so two live instruction
        files cite different numbers for the same mechanism. Concretely, after
        ADR-0031 Decision 6 the repo simultaneously carried
        ``.claude/skills/committing-changes/SKILL.md`` saying "#3 requires
        independent evaluation" and ``.claude/rules/testing_requirements.md``
        saying independence was "#4". Both numbers are in range, so nothing
        detected it.

        Coverage is keyword-bounded — see the module docstring. A line only gets
        checked if its wording matches CONCEPT_KEYWORDS.
        """
        unexpected: dict[str, list[str]] = {}
        for rel in live_instruction_files():
            text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
            hits = wrong_concept_hits(text, concept_slots)
            entry = KNOWN_STALE_CITATIONS.get(rel)
            allowed = entry.wrong_concept if entry else 0
            if len(hits) > allowed:
                unexpected[rel] = [f"{len(hits)} hits, {allowed} registered", *hits]

        assert not unexpected, (
            "live instruction files cite the wrong principle number for a concept they "
            f"name, more often than their KNOWN_STALE_CITATIONS entry allows: {unexpected}. "
            "The number is in range, so the out-of-range check cannot see it — this is the "
            "two-files-two-numbers failure ADR-0031 Decision 6's renumber was most likely "
            "to cause."
        )

    def test_known_stale_allowlist_does_not_rot(
        self, principles: list[tuple[int, str]], concept_slots: dict[str, int]
    ) -> None:
        """A registered entry must name a file that exists and violate EXACTLY as recorded.

        Both directions matter. Too few violations means the debt was paid and the
        entry is now dead cover — that is how a fixed file keeps a permanent
        exemption and the next bad citation in it goes unseen. Too many means a new
        violation slipped in (the checks above will already have failed, but this
        says so in terms of the register).

        The counts are the whole point of the count-scoped design: an entry buys
        silence about a specific number of known-bad lines, never about a file.
        """
        missing = [p for p in KNOWN_STALE_CITATIONS if not (REPO_ROOT / p).exists()]
        assert not missing, (
            f"KNOWN_STALE_CITATIONS names paths that no longer exist: {missing}. "
            "Delete the entries."
        )

        highest = len(principles)
        drifted: dict[str, str] = {}
        for rel, entry in KNOWN_STALE_CITATIONS.items():
            text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
            measured = (
                len(out_of_range_hits(text, highest)),
                len(wrong_concept_hits(text, concept_slots)),
            )
            registered = (entry.out_of_range, entry.wrong_concept)
            if measured != registered:
                verb = "DELETE the entry" if measured == (0, 0) else "update the numbers to"
                drifted[rel] = (
                    f"registered (out_of_range={registered[0]}, wrong_concept={registered[1]}) "
                    f"but measured (out_of_range={measured[0]}, wrong_concept={measured[1]}) "
                    f"-> {verb} {measured}"
                )

        assert not drifted, (
            f"KNOWN_STALE_CITATIONS is out of date: {drifted}. An entry that over-counts is "
            "dead cover for violations that no longer exist; an entry that under-counts means "
            "a new bad citation landed. Either way the register must be re-measured, never "
            "widened to make the suite green."
        )


class TestConceptBindingCoverage:
    """The guard's own reach is a measured number, not a caveat in a docstring."""

    def test_concept_binding_coverage_has_not_regressed(
        self, concept_slots: dict[str, int], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Assert a floor on the fraction of citation lines the concept check can inspect.

        The wrong-but-in-range check is keyword-bounded: it forms an opinion only
        about lines whose wording appears in ``CONCEPT_KEYWORDS``. That makes
        "15 passed" quietly ambiguous — it could mean "nothing is wrong" or "the
        module was not taught the words for the thing that is wrong". Measuring the
        fraction turns the ambiguity into a number, and asserting a floor stops the
        number drifting down as new citation lines arrive in new phrasings.

        Measured at 33/36 = 91.7% when this floor was set. The three unreachable
        lines are enumerated in the module docstring.
        """
        bound, total, unbound = concept_binding_coverage(concept_slots)
        assert total, "no citation lines found at all — the scan is broken, not the corpus"
        coverage = bound / total

        with capsys.disabled():
            print(
                f"\nconcept-binding coverage: {bound}/{total} = {coverage:.1%} "
                f"(floor {MIN_CONCEPT_COVERAGE:.0%})"
            )
            for line in unbound:
                print(f"  UNCHECKED {line}")

        assert coverage >= MIN_CONCEPT_COVERAGE, (
            f"concept-binding coverage fell to {coverage:.1%} ({bound}/{total}), below the "
            f"{MIN_CONCEPT_COVERAGE:.0%} floor. Unchecked citation lines: {unbound}. "
            "Either teach CONCEPT_KEYWORDS the new phrasing (measure for false positives on "
            "the clean tree first) or give the citation a concept anchor in its own text — "
            "'Principle #7 (clarify before acting)' is checkable, bare 'Principle #7' is not."
        )

    def test_every_concept_keyword_matches_something(self, concept_slots: dict[str, int]) -> None:
        """A keyword that matches nothing inflates apparent coverage without adding reach.

        Three dead keywords shipped in the first version of this module and one of
        them ("reward function" written with a space when the corpus hyphenates it)
        had been added specifically to cover a line in CLAUDE.md — so the line the
        keyword existed for was the line it failed to check. Dead keywords are
        therefore not cosmetic.

        ``ALLOWED_DEAD_KEYWORDS`` is the deliberate exception list, and it is short.
        """
        allowed_dead = {
            # ASCII spelling of "builder ≠ checker"; the glyph form matches today
            # and the ASCII form must not slip through if someone types it.
            "builder != checker",
        }
        corpus = "\n".join(
            (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace").lower()
            for rel in live_instruction_files()
        )
        dead = sorted(
            keyword
            for keywords in CONCEPT_KEYWORDS.values()
            for keyword in keywords
            if keyword not in allowed_dead and keyword.lower() not in corpus
        )
        assert not dead, (
            f"CONCEPT_KEYWORDS entries match nothing on the live surface: {dead}. "
            "Either the corpus phrases the concept differently (fix the keyword to the "
            "phrasing actually used) or the keyword is aspirational (move it to "
            "allowed_dead with a reason). A dead keyword makes the coverage number lie."
        )


class TestGovernanceLocationClaims:
    """When the constitution says a rule lives in file X, file X must contain the rule."""

    @pytest.mark.regression
    def test_governance_claims_name_files_that_contain_the_mechanism(self) -> None:
        """Regression guard: inert prose that reads as a mechanism.

        The motivating failure is measured, not hypothetical. ``CLAUDE.md`` and
        ``PHILOSOPHY.md`` (in two places) each asserted that review plurality was
        "specified in ``/review``". ``.claude/commands/review.md`` contained zero
        occurrences of "plurality", zero references to the ``selecting-review-gates``
        skill, and no numeric panel floor — so the constitution documented a safety
        guarantee whose stated home was empty, and every test in this module was
        green while it did so.

        The check is general on purpose. It reads the claim out of the constitution,
        resolves whatever file the claim names, and demands the mechanism be there.
        Adding a mechanism to ``GOVERNANCE_MECHANISMS`` guards every future sentence
        that claims a home for it, including sentences nobody has written yet.
        """
        violations: list[str] = []
        for mechanism in GOVERNANCE_MECHANISMS:
            for rel in CLAIMING_FILES:
                text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
                for line_no, block in claim_blocks(text):
                    lowered = block.lower()
                    if not any(marker in lowered for marker in mechanism.claim_markers):
                        continue
                    for token in location_claim_targets(block):
                        target = resolve_reference(token)
                        if target is None:
                            violations.append(
                                f"{rel}:{line_no} claims {mechanism.name} is in {token!r}, "
                                "which does not resolve to any file in this repo"
                            )
                            continue
                        body = (
                            (REPO_ROOT / target)
                            .read_text(encoding="utf-8", errors="replace")
                            .lower()
                        )
                        absent = [m for m in mechanism.required_markers if m not in body]
                        if absent:
                            violations.append(
                                f"{rel}:{line_no} says {mechanism.name} is specified in "
                                f"{target}, but that file is missing {absent}"
                            )

        assert not violations, (
            "the constitution names a home for a governance mechanism that does not "
            f"contain it: {violations}. Either put the mechanism in the file the "
            "constitution names, or stop naming that file. A governance guarantee that "
            "points at an empty file is the assert-don't-measure defect applied to a "
            "safety mechanism — it reads exactly like a working guard."
        )

    def test_each_mechanism_has_at_least_one_live_claim(self) -> None:
        """Guard the guard: a rephrase must not silently make the check vacuous.

        ``test_governance_claims_name_files_that_contain_the_mechanism`` passes
        trivially if it finds no claims — which is exactly what happens if someone
        rewrites the constitutional sentence using a location phrase
        ``_LOCATION_PHRASE`` does not know. Without this test, deleting the guarantee
        from the constitution would look like a fix.
        """
        for mechanism in GOVERNANCE_MECHANISMS:
            found: list[str] = []
            for rel in CLAIMING_FILES:
                text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
                for line_no, block in claim_blocks(text):
                    lowered = block.lower()
                    if not any(marker in lowered for marker in mechanism.claim_markers):
                        continue
                    found.extend(f"{rel}:{line_no} -> {t}" for t in location_claim_targets(block))
            assert found, (
                f"no location claim for {mechanism.name!r} was found in {list(CLAIMING_FILES)}. "
                "Either the constitution stopped saying where this mechanism lives (put the "
                "sentence back — the guarantee is what the mechanism is for), or it was "
                "rephrased using wording _LOCATION_PHRASE does not recognise (add the phrase). "
                "Silence here makes the location check vacuous."
            )


class TestPluralityLanded:
    """Retired main #3's plurality half had to land somewhere concrete, not merely go unsaid."""

    def test_selecting_review_gates_states_numeric_panel_floors(self) -> None:
        """The skill must state NUMBERS, not merely use the word "plurality".

        The first version of this test asserted only that the word appeared
        somewhere in the file. That is satisfied by a sentence about plurality
        which specifies nothing — the same "reads like a mechanism, is not one"
        shape the location check exists to catch. A floor a dispatcher cannot
        act on is not a floor.
        """
        floors = plurality_floors()
        assert floors == PLURALITY_FLOORS, (
            f"{PLURALITY_SKILL} states panel floors {floors}, expected {PLURALITY_FLOORS}. "
            "These numbers are implementation-chosen under ADR-0031 Decision 6's disposition, "
            "not stated by the ADR (see PROVENANCE beside PLURALITY_FLOORS). Changing one is "
            "still a governance decision under the Framework Evolution clause — Steward gate "
            "then developer approval — and the ADR that records the new number and this "
            "assertion move together, never this assertion alone."
        )

    @pytest.mark.regression
    def test_plurality_floors_do_not_drift(self) -> None:
        """Every live file that restates a panel floor must state the same number.

        Plurality is now stated in one normative place and is expected to be
        restated where panels are actually dispatched. Two copies of a safety
        floor is how a floor quietly becomes two different floors — so any live
        instruction file that mentions plurality and attaches a number to a risk
        tier must agree with the skill.

        This is order-independent by design: it is green while only the skill
        carries the block, green when a second file carries an identical copy,
        and red the moment two copies disagree.
        """
        canonical = plurality_floors()
        violations: list[str] = []
        for rel in live_instruction_files():
            if rel == PLURALITY_SKILL:
                continue
            text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
            if "plurality" not in text.lower():
                continue
            for tier, number in _restated_floors(text):
                if tier in canonical and number != canonical[tier]:
                    violations.append(
                        f"{rel} states {tier} risk = {number} specialists; "
                        f"{PLURALITY_SKILL} states {canonical[tier]}"
                    )

        assert not violations, (
            f"panel-size floors disagree across live files: {violations}. One of the two "
            "copies was edited alone. The floors have a single normative home "
            f"({PLURALITY_SKILL}); every restatement must match it verbatim."
        )

    def test_philosophy_records_both_relocations(self, philosophy_text: str) -> None:
        """PHILOSOPHY.md is where main #8 was moved and where the refusals are re-pointed."""
        lowered = philosophy_text.lower()
        assert "growth has a brake" in lowered, (
            "PHILOSOPHY.md must carry the relocated home for retired main #8 "
            "(least-complex intervention, the growth-side brake)."
        )
        assert "authoritative single-source answers" in lowered, (
            "PHILOSOPHY.md's refusal list must keep 'authoritative single-source answers' — "
            "ADR-0031 Decision 6 re-points it to plurality rather than deleting it."
        )
        assert "captive dependency" in lowered, (
            "the accidental-complexity refusal survives main #8's retirement and must stay named."
        )

    @pytest.mark.regression
    def test_every_restatement_of_the_block_is_verbatim(self) -> None:
        """A restated safety block must match the normative one byte for byte.

        ``PLURALITY_SKILL`` claims in prose that ``/review`` "carries a
        byte-identical copy of the block above". Until this test existed that was
        an assertion, not a measurement: ``test_plurality_floors_do_not_drift``
        compares tier->number pairs only, so a copy could keep "at least 3" while
        losing the clause that defines what *independent* means — and the skill's
        sentence would still read as if something enforced it.

        Both halves are guarded. The copy must be identical, and the dispatching
        command must be among the restaters, so deleting the block from
        ``/review`` fails here rather than quietly making the check vacuous.
        """
        canonical = plurality_block(
            (REPO_ROOT / PLURALITY_SKILL).read_text(encoding="utf-8", errors="replace")
        )
        assert canonical is not None, (
            f"{PLURALITY_SKILL} no longer carries the panel-size block "
            f"({PLURALITY_BLOCK_HEADING!r} through {PLURALITY_BLOCK_END!r}). It is the "
            "normative home for review plurality — the floors have to live somewhere "
            "concrete or the constitution is pointing at nothing."
        )

        restaters = plurality_restaters()
        assert PLURALITY_DISPATCH_COMMAND in restaters, (
            f"{PLURALITY_DISPATCH_COMMAND} does not carry {PLURALITY_BLOCK_HEADING!r}. "
            f"{PLURALITY_SKILL} names that command as carrying a byte-identical copy, and it "
            "is the file a dispatcher actually reads while assembling a panel. Restore the "
            "copy, or stop claiming it exists."
        )

        mismatched: list[str] = []
        for rel in restaters:
            copy = plurality_block((REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace"))
            if copy is None:
                mismatched.append(f"{rel}: has the heading but not the full block")
                continue
            if copy != canonical:
                diff = "\n".join(
                    difflib.unified_diff(
                        canonical.splitlines(),
                        copy.splitlines(),
                        fromfile=PLURALITY_SKILL,
                        tofile=rel,
                        lineterm="",
                    )
                )
                mismatched.append(f"{rel}:\n{diff}")

        assert not mismatched, (
            "a restatement of the panel-size block is not byte-identical to "
            f"{PLURALITY_SKILL}:\n\n" + "\n\n".join(mismatched) + "\n\n"
            "One copy was edited alone. Edit the skill (the normative home) and propagate the "
            "exact text, or the two copies become two different safety rules."
        )


class TestProseReferencesResolve:
    """Prose that names a test as its enforcement must name a test that exists."""

    @pytest.mark.regression
    def test_cited_pytest_node_ids_exist(self) -> None:
        """A node id in an instruction file is a location claim about a guard.

        ``.claude/skills/selecting-review-gates/SKILL.md`` tells the reader which
        tests hold the panel-size floors in place; ``CLAUDE.md``'s Known
        Limitations names the regression test for the MCP thread-local model.
        Renaming or deleting those tests leaves the sentence intact and the guard
        gone — the same defect as a governance mechanism whose stated home is
        empty, which is why it is checked the same way.
        """
        index = node_id_index()
        assert index, "no test modules found under tests/ — the resolver is broken, not the prose"
        broken = unresolved_node_ids(index)
        assert not broken, (
            f"live instruction prose names pytest node ids that do not resolve: {broken}. "
            "A renamed test leaves the sentence reading like a working guard. Either update "
            "the prose to the new node id or restore the test it names."
        )

    def test_the_resolver_is_not_vacuous(self) -> None:
        """Guard the guard: the check above passes trivially if nothing is cited.

        References live in the plurality block's own explanation, in
        ``severity-calibration``, and in ``CLAUDE.md``'s Known Limitations. No
        expected count is written down here on purpose — a hardcoded tally in a
        docstring is exactly the kind of unmeasured number this module exists to
        catch, and it would rot the first time a citation was added or removed.
        The assertion is only that the number is not zero, which is the one value
        that would make the check above vacuous: either the prose pointing
        readers at the enforcement was deleted, or the reference patterns stopped
        matching how the corpus writes them.
        """
        index = node_id_index()
        cited = 0
        for rel in live_instruction_files():
            text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
            cited += len(_FULL_NODE_ID.findall(text)) + len(_BARE_NODE_ID.findall(text))
        assert cited, (
            "no pytest node id is cited anywhere on the live instruction surface, so "
            "test_cited_pytest_node_ids_exist asserts nothing. Either the prose that points "
            "readers at the enforcing tests was removed, or _FULL_NODE_ID/_BARE_NODE_ID no "
            f"longer match the way it is written. Test modules indexed: {len(index)}."
        )
