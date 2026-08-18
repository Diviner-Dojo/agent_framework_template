r"""Check a build's recorded paths-not-taken against the diff that actually shipped.

Why this script exists
----------------------
`/plan` and `/build_module` now ask the builder to record, *at the moment of the
choice*, what it decided **against**. A self-reported "alternatives considered"
is exactly the artifact that rots into a comfortable fiction: it is written by
the party it flatters, and nothing reads it back. This file is what reads it
back.

**What this file is NOT, stated first because an earlier draft claimed the
opposite.** It is not Principle #2. Principle #2 is capture enforced by scripts
and hooks *rather than by instruction*, and nothing invokes this script::

    $ grep -rn "verify_paths_not_taken" scripts/ .claude/ config/ pyproject.toml \
        | grep -v "^scripts/verify_paths_not_taken.py"
    (10 hits, every one of them markdown instruction text in
     .claude/commands/{plan,build_module,review}.md — no caller)

There is no hook, no quality-gate check, and no pre-commit wiring. Running this
file depends entirely on an agent choosing to be diligent, which is the same
dependency the prose it replaces had. What it actually buys is **Principle #3**:
the record is written by the builder and re-run by a *separate context* that did
not write it, against the diff rather than against the story. That is a real
property and a smaller one. Claiming #2 here while `ADR-0034` retracts it would
be the command/checker drift this file's own test suite exists to catch, living
in the file that suite guards.

What it can decide, and what it cannot
--------------------------------------
Three failure cases were named as the target. This script reaches two and a
half of them, and the split is deliberate — an unfalsifiable claim about the
checker is the same defect as an unfalsifiable claim about the code.

* **CONTRADICTED (case 1) — partially mechanical.** A record must name a
  ``Falsifier``: a literal string that *would appear in the added lines* if the
  rejected approach had actually been taken. If that string is present in the
  diff's added lines **within the record's own files**, the record is refuted.
  This catches the contradiction the builder was willing to make checkable. It
  does NOT catch a semantic contradiction — "we rejected an in-process cache"
  while the diff adds a dict that is one — because no string comparison can.
  That half stays with the briefing agent, on purpose.
* **PHANTOM — mechanical.** A record whose ``Files`` name nothing the diff
  touched describes a decision that did not land here. Also a case-1 shape: the
  diff contradicts the claim's location.

  .. warning::

     PHANTOM is only as honest as the diff it is handed. ``git diff`` does not
     show **untracked** files, so a diff taken without ``git add
     --intent-to-add`` reports every record about a NEW file as PHANTOM —
     measured: a 40-line untracked ``src/new_module.py`` gives ``git diff HEAD``
     of **0 bytes**, and after ``--intent-to-add`` the same diff reports
     **1 file changed, 40 insertions(+)**. That is a false refutation of a true
     record, i.e. this instrument's own worst failure mode, so the PHANTOM
     message names the cause whenever the missing path is present on disk, and
     both calling commands prescribe the ``--intent-to-add`` line. If you invoke
     this script by hand, take the diff the same way.

     The after-figure used to be quoted here as a byte size ("488 bytes"), and
     that number was not a property of the shape named beside it. Measured over
     the eight combinations of ``src/``-vs-root path x trailing-newline-vs-not x
     LF-vs-CRLF, the diff runs 448/460/476/488/500/515/527 bytes; 488 lands on
     two of them (``src/new_module.py`` LF with no trailing newline, and root
     ``new_module.py`` CRLF with one), so the figure could not be read back to a
     single shape. The insertion count is **40** in all eight, which is why the
     sentence above quotes that instead. ``tests/test_paths_not_taken.py``
     re-derives it from a real repo rather than trusting this paragraph.
* **UNFALSIFIABLE (case 2) — mechanical.** Missing field, blank field, a
  ``Files`` list with nothing path-shaped in it, or a ``Falsifier`` too short or
  drawn from :data:`VAGUE_FALSIFIERS`. This is a *structural* judgement: it
  catches a record nobody could ever check, not a record that is merely weak.
  A falsifier that is precise-looking but wrong (``FooBar`` when the rejected
  approach would have been spelled ``Foo_Bar``) is indistinguishable from a
  falsifier that is precise and right, and passes here.
* **UNRECORDED (case 3) — a PROXY, and the weakest of the four.** The script
  cannot see decisions; it sees files. It flags a changed file that no record
  names and whose churn crosses ``--min-changed-lines``, MINUS the paths in
  :data:`DEFAULT_EXCLUDES` (see there for why a default set exists at all, and
  what it costs). A real decision made inside a three-line hunk is invisible to
  it, and a large mechanical rename is flagged though it decided nothing. Read
  exit 2 as "these files were never spoken for", never as "these files contain
  unrecorded decisions".

The false-POSITIVE side, which the four bullets above do not state
-----------------------------------------------------------------
A limits section that lists only false negatives is itself a comfortable
fiction. These are the ways this script can be **wrong about a true record** —
the direction that matters most, because a blocking verdict against honest work
is how you teach people to stop recording:

* **A falsifier that appears in prose is not a contradiction.** Writing a
  comment that explains why you rejected an approach is practice this framework
  encourages, and a bare substring test refutes your own truthful record for
  doing it. So added lines that are **comments** (:data:`COMMENT_PREFIXES`) or
  that live in a **prose file** (:data:`PROSE_SUFFIXES`) cannot produce
  CONTRADICTED. They produce the advisory ``CONTRADICTED-IN-PROSE`` instead,
  which is reported but does **not** fail the run. The cost is a real false
  negative, and it is **not a small one — measure it before trusting a green
  run**: over all 143 non-merge commits reachable from HEAD (1509 file-touches),
  **64.8%** of the touches that reach :data:`DEFAULT_MIN_CHANGED_LINES` (577 of
  891) are prose files, because this repo's changes are dominated by markdown
  commands, skills and rules. So CONTRADICTED — the only check that tests a
  record's TRUTH — is switched off for roughly two thirds of the file-touches it
  would otherwise judge, and on a markdown-only governance change it is switched
  off entirely. Read exit 0 on such a change as "nothing was structurally broken
  and nothing was refuted *in code*", never as "no record was refuted". That
  trade is deliberate — a false refutation of a truthful record is the outcome
  that teaches people to stop recording — but it is stated with its size here,
  in ``/review`` Step 6.4, and re-measured in ``tests/test_paths_not_taken.py``,
  rather than left to be discovered by someone over-trusting a green run.
* **String matching cannot see scope.** The falsifier is searched in whole added
  lines, so a docstring, a test asserting the rejected approach is *absent*, or a
  string literal quoting it still matches when the line is not a comment. The
  advisory kind exists partly so this class is visible without being blocking.

  **Observed live, 2026-08-09 — this is not hypothetical.** Re-running the
  Steward's fabricated-record probe (falsifier ``_STATUS_REGISTRY_GLOBAL``)
  against the diff of THIS file returned ``VERIFICATION FAILED``, exit 1,
  ``CONTRADICTED`` — because the warning above *documents* the probe and
  therefore adds a line naming its falsifier. The line sits inside this module
  docstring, but it does not itself begin with a triple-quote marker, so
  :func:`is_prose_line` reads it as code and the carve-out never applies. A
  truthful record was refuted by the act of documenting it. Against the
  unmodified pre-fix diff the same probe returns
  ``MECHANICALLY-CLEAR``, exit 0. **Multi-line string bodies are the gap**: only
  the OPENING line of a docstring carries a marker, so the triple-quote entries
  in :data:`COMMENT_PREFIXES` reach the first line of a docstring and none of
  the rest. Fixing it needs a real parse (``ast``/``tokenize``) rather than a
  prefix test, which is a larger change than this instrument has earned; it is
  stated here instead. If a ``CONTRADICTED`` verdict points at a line inside a
  docstring, read the file before believing it.
* **Deletions are read, not ignored.** A ``+++ /dev/null`` hunk is attributed to
  the path from its ``--- a/<path>`` header, so "we deleted the module rather
  than keep a shim" is a checkable record and a vanished file counts toward the
  coverage proxy. A deleted file has no added lines, so it can never be
  CONTRADICTED — only PHANTOM (if the record names some other file) or
  UNRECORDED.
* **A payload line is never mistaken for a file header.** Hunk boundaries are
  read from the ``@@`` counts, so a removed line beginning ``-- `` or an added
  line beginning ``++ `` stays content. Measured with real ``git diff`` before
  the fix: one markdown file that removed ``-- old sql comment`` and added
  ``++ new marker line`` parsed as churn 0 for that file — silently dropping it
  out of the coverage proxy and out of any contradiction check — plus a phantom
  path ``new marker line`` in the changed-file set. ``-- `` lines are live in
  this repo's own markdown. The residual gap is stated rather than fixed: a diff
  whose ``@@`` header is unreadable falls back to the permissive reading, where
  that confusion is again possible.

Exit codes (a caller MUST branch on these; they are the contract)
-----------------------------------------------------------------
* ``0`` — MECHANICALLY-CLEAR: no record was structurally broken, none was
  refuted **in code**, and every qualifying file is spoken for. The summary
  always prints the two counts that make a vacuous pass visible: a run over zero
  records and zero qualifying files says so in words.

  .. warning::

     **Exit 0 is deliberately NOT called VERIFIED, and the word is the fix.**
     Everything above already said that exit 0 means "nothing refuted *in
     code*" — and the verdict this script PRINTED said ``VERIFIED``, which is
     the word that travelled into ``/review``'s hand-off, into a review report,
     and eventually to a developer being taught. Measured 2026-08-09 against a
     record written to be false on purpose (a straw-man alternative rejected for
     a reason obvious before any work began, and a falsifier — ``_STATUS_REGISTRY_GLOBAL``
     — invented to be absent by construction) checked against this file's own
     1099-line diff: the old build printed
     ``PATHS_NOT_TAKEN: VERIFIED -- 1 record(s) checked`` at exit 0. Nothing in
     that run was verified; a fabrication passed because the only thing this
     script can test is whether a string is present. So the verdict word is now
     :data:`VERDICT_WORDS`\ ``[EXIT_OK]`` = ``MECHANICALLY-CLEAR`` — the same
     word ``/review`` Step 7 already used for a per-record status — and
     :data:`CLEAR_CAVEAT` is printed beside it in both output modes. A tool
     whose prose says one thing and whose headline says another is judged on the
     headline. Only a reader who checks whether the rejected option was ever
     real can award ``VERIFIED``, and that verdict belongs to the briefing agent
     (``/review`` Step 10 obligations 2-3), never to this file.
* ``1`` — VERIFICATION FAILED: at least one CONTRADICTED, PHANTOM, or
  UNFALSIFIABLE record. A claim is wrong or uncheckable.
* ``2`` — COVERAGE GAP only: every record held up, but files changed that no
  record speaks for. ``CONTRADICTED-IN-PROSE`` is advisory and does not reach
  either failing code; it is reported for the briefing agent to adjudicate.
* ``3`` — INSTRUMENT FAILURE: the events file or the diff could not be read or
  parsed. Never conflated with 0. A verifier that cannot read its own evidence
  reporting "clean" is the failure this whole mechanism exists to stop.

Usage::

    python scripts/verify_paths_not_taken.py --list-sources
    python scripts/verify_paths_not_taken.py --events <events.jsonl> --diff <diff|->
    python scripts/verify_paths_not_taken.py --discussion DISC-plan
        --discussion DISC-build --diff -

``--events`` and ``--discussion`` are both repeatable and combine: a spec-driven
change has design alternatives in the ``/plan`` discussion and implementation
alternatives in the ``/build_module`` one, and both are claims about one diff.

``--list-sources`` is the ENTRY POINT, and it exists because the mechanism did not
have one. A reviewer who is not handed the two discussion ids has only the
documented fallback (``NOT RUN``), which is frictionless, so ``NOT RUN`` would
have been the path of least resistance for every build-driven review and the check
would have become prose while still reading as a mechanism. ``--list-sources``
prints every discussion that actually holds records, newest first. It does **not**
auto-select them: verifying an unrelated older discussion against today's diff
would report its truthful records as PHANTOM, and a blocking verdict against
honest work is the failure this instrument must not have.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DISCUSSIONS_DIR = PROJECT_ROOT / "discussions"

#: The heading that opens one record. Chosen to match the corpus's existing
#: ``## Request Context`` block convention rather than inventing a new syntax.
RECORD_HEADING = "## Path Not Taken"

#: Tag that marks an event as carrying records. Events are read by TAG, not by
#: agent or intent, so any workflow can contribute one.
RECORD_TAG = "path-not-taken"

#: Every field a record must carry. Order is the order they are written in.
REQUIRED_FIELDS: tuple[str, ...] = (
    "decision",
    "chosen",
    "rejected",
    "why rejected",
    "files",
    "falsifier",
)

#: Falsifiers that name nothing checkable. Lowercased exact match after strip.
#: Kept short on purpose: this list is meant to catch the shrug, not to grade
#: prose. Anything longer starts refusing honest records.
VAGUE_FALSIFIERS: frozenset[str] = frozenset(
    {
        "n/a",
        "na",
        "none",
        "nothing",
        "unknown",
        "tbd",
        "various",
        "etc",
        "the other approach",
        "a different approach",
        "another approach",
        "the alternative",
        "an alternative",
        "the rejected approach",
        "see above",
    }
)

#: Shortest falsifier that can plausibly identify code. Three characters or
#: fewer matches half a codebase, which would turn every record into a false
#: CONTRADICTED and teach people to stop recording.
MIN_FALSIFIER_LENGTH = 4

#: Line prefixes that mark an added line as a comment rather than as code taking
#: an approach. A falsifier found on one of these is reported as the advisory
#: ``CONTRADICTED-IN-PROSE`` and never as a blocking CONTRADICTED — writing a
#: comment that explains a rejection must not refute the record of it.
#:
#: ``-- `` and ``* `` carry a TRAILING SPACE deliberately, and the space is the whole
#: fix. Measured on the bare markers: ``is_prose_line('scripts/x.sh', '--patch-guard \\')``
#: and ``is_prose_line('src/a.py', '*args,')`` both returned True, so a genuine code line
#: beginning with one of ``/build_module``'s own taught-good falsifiers (``--patch-guard``
#: is example 3 of 4) was downgraded from CONTRADICTED to advisory — the command taught an
#: example its own checker was partly blind to. Requiring the space keeps the real comment
#: shapes (``-- sql comment``, a C block-comment continuation `` * text``) while letting
#: ``--flag``, ``*args`` and ``**kwargs`` through as code.
#: ``tests/test_paths_not_taken.py`` re-derives the taught-good examples from the command
#: text and asserts each is seen as code, so re-broadening this tuple fails there.
COMMENT_PREFIXES: tuple[str, ...] = ("#", "//", "/*", "-- ", "* ", "<!--", ";", '"""', "'''")

#: File suffixes whose added lines are prose end to end, so the same rule applies
#: to every line in them, comment marker or not.
#:
#: .. warning::
#:
#:    **This is where CONTRADICTED — the only check that tests a record's TRUTH — is
#:    switched off, and in THIS repo that is the majority case, not an edge case.**
#:    Measured 2026-08-09 over all 143 non-merge commits reachable from HEAD (1509
#:    file-touches by ``git show --numstat``): 798 touches (52.9%) carry a prose suffix,
#:    and restricted to the 891 touches whose churn reaches
#:    :data:`DEFAULT_MIN_CHANGED_LINES` — the ones the coverage proxy asks about — 577 of
#:    891 are prose, i.e. **64.8%**. A hub-governance change (commands, skills, rules) is
#:    markdown end to end, so for the changes this repo mostly makes, exit 0 means "no
#:    record was structurally broken and none was refuted *in code*", NOT "no record was
#:    refuted". The remaining kinds (PHANTOM, UNFALSIFIABLE, UNRECORDED) still apply at
#:    full strength. The behaviour is deliberate — a false refutation of a truthful record
#:    is this instrument's worst outcome — but the size of the hole is stated here, and
#:    re-measured by ``tests/test_paths_not_taken.py``, rather than left to be discovered.
PROSE_SUFFIXES: tuple[str, ...] = (".md", ".markdown", ".rst", ".txt")

#: Default churn (added + removed lines) at which an unspoken-for file is
#: reported. The number is a judgement, but an evidenced one. Measured
#: 2026-08-09 over ALL 143 non-merge commits then reachable from HEAD — asking
#: git for 200 returns 143, which is the whole history of this branch, so it is
#: not a "last 200" sample — 1509 file-touches by ``git show --numstat``: median
#: per-file churn is 44 lines and this threshold selects 59.0% of touched files.
#: 20 was chosen to sit clearly below the median so a normal edit is asked to
#: account for itself, while 5 (83.8%) would make the proxy fire on nearly
#: everything and 50 (48.0%) would let a median change through unspoken-for.
#: ``tests/test_paths_not_taken.py`` RE-MEASURES this rather than trusting the
#: numbers above, so the justification rots loudly. Tunable with
#: ``--min-changed-lines``; re-measure before trusting it in a different corpus.
DEFAULT_MIN_CHANGED_LINES = 20

#: Paths the coverage proxy does not ask anyone to speak for, applied unless the caller
#: passes ``excludes=[]`` / ``--no-default-excludes``. fnmatch globs, and note fnmatch's
#: ``*`` crosses ``/``, so ``discussions/*`` already means the whole subtree.
#:
#: **Why a default set exists at all.** Shipped without one, exit 2 was the ordinary verdict
#: and an advisory that fires every run stops being read. Measured 2026-08-09 over the last
#: 30 non-merge commits (``git show --numstat --format= -1 <sha>``, counting files whose
#: churn reaches :data:`DEFAULT_MIN_CHANGED_LINES`): 155 qualifying touches, median 3.5 and
#: mean 5.17 per commit. With this set: **111 touches, median 3.0, mean 3.70** — a 28.4%
#: cut, and the per-glob contributions are discussions/ 26, docs/reviews/ 13,
#: BUILD_STATUS.md 5, metrics/ 0-in-history (but live: ``metrics/quality_gate_log.jsonl``
#: was 41 changed lines in the working tree this was written from, and it churns on every
#: gate run). ``tests/test_paths_not_taken.py`` re-derives those numbers from git.
#:
#: **The entry that is not merely noise-reduction.** ``discussions/*`` closes a
#: SELF-INFLICTED loop: Layer 1 grows *because* the builder wrote path-not-taken records,
#: so writing more records pushed your own ``events.jsonl`` over the churn threshold and got
#: it reported unspoken-for. A proxy that penalises the behaviour it exists to encourage is
#: not tuned, it is inverted.
#:
#: **What is deliberately NOT here, and the cost of that.** ``tests/*`` is the single
#: largest remaining category (26 of 155, tied with discussions/) and excluding it would
#: take the median to 2.0. It is kept in scope because "a test file cannot hold a design
#: decision" is false in this repo specifically: ``tests/test_paths_not_taken.py``'s own
#: header records choosing relation-assertions over literal-assertions and keeping two
#: literal exceptions on purpose — a path not taken, living in ``tests/``. Excluding the
#: tree would tell a builder that test-design choices never need recording. ``docs/`` is
#: likewise only excluded at ``docs/reviews/`` (generated review output): ``docs/adr/`` (10
#: qualifying touches) and ``docs/sprints/`` (7) are where design decisions are SUPPOSED to
#: land, so a blanket ``docs/*`` would blind the proxy to its best material.
DEFAULT_EXCLUDES: tuple[str, ...] = (
    "discussions/*",
    "docs/reviews/*",
    "metrics/*",
    "BUILD_STATUS.md",
)

#: Problem kinds that are REPORTED but do not make the run fail. Anything not
#: listed here forces :data:`EXIT_FAILED`, so adding a kind without deciding its
#: severity fails closed.
ADVISORY_KINDS: frozenset[str] = frozenset({"UNRECORDED", "CONTRADICTED-IN-PROSE"})

#: Emitted whenever the run asserted almost nothing. It lives in the RESULT, not
#: only in the rendered text, because ``--json`` is the mode ``/review`` actually
#: invokes and a note only the text mode prints is absent exactly where it was
#: needed.
VACUOUS_NOTE = (
    "nothing was recorded AND no file crossed the churn threshold, so this run "
    "asserted almost nothing. Do not read it as evidence the change had no "
    "decisions in it."
)

#: A unified-diff hunk header. The two optional counts are what bound the hunk, and the bound is
#: what stops a payload line that merely LOOKS like a ``+++ ``/``--- `` header from being read as
#: one.
_HUNK_RE = re.compile(r"@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@")

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_COVERAGE_GAP = 2
EXIT_INSTRUMENT_FAILURE = 3

#: Exit code -> the verdict word this script prints for it. Exported so every other
#: surface (``/review``, ``/build_module``, the guard suite) reads the word from HERE
#: instead of restating it. ``EXIT_OK`` is ``MECHANICALLY-CLEAR`` and never ``VERIFIED``
#: — see the exit-code warning in the module docstring for the measurement that forced
#: the rename. The word is a claim about what ran, and what ran is a string search.
VERDICT_WORDS: dict[int, str] = {
    EXIT_OK: "MECHANICALLY-CLEAR",
    EXIT_FAILED: "VERIFICATION FAILED",
    EXIT_COVERAGE_GAP: "COVERAGE GAP",
    EXIT_INSTRUMENT_FAILURE: "INSTRUMENT FAILURE",
}

#: Printed beside every exit-0 verdict, in BOTH output modes and in the ``--json``
#: payload. A one-word verdict is what gets quoted; this is the sentence that stops
#: the quote from meaning more than the run did.
CLEAR_CAVEAT = (
    "MECHANICALLY-CLEAR is not VERIFIED. It means no record was structurally broken and "
    "none was refuted IN CODE -- a fabricated record whose falsifier is absent by "
    "construction passes every check in this file. Whether the rejected option was ever "
    "real is a reader's judgement (/review Step 10 obligations 2-3), not this script's."
)

#: The status this script assigns a record it could not refute. Deliberately the same
#: token ``/review``'s hand-off block already required, so the two sides cannot drift
#: into two vocabularies for one fact.
STATUS_CLEAR = "MECHANICALLY-CLEAR"

#: Problem kinds, worst first. A record can draw more than one — a CONTRADICTED hit in
#: one of its files and a CONTRADICTED-IN-PROSE hit in another — and the per-record
#: status must report the WORST, or an advisory would mask a refutation.
STATUS_PRECEDENCE: tuple[str, ...] = (
    "CONTRADICTED",
    "PHANTOM",
    "UNFALSIFIABLE",
    "CONTRADICTED-IN-PROSE",
)

#: Every value ``record_status[*]["status"]`` can take. This is the vocabulary
#: ``/review`` Step 7 promises the briefing agent, and ``tests/test_paths_not_taken.py``
#: asserts the command's list and this tuple are the same set — the promise used to be
#: made by the command and kept by nobody, because the result carried only a flat
#: ``problems`` list with no per-record status in it at all.
RECORD_STATUSES: tuple[str, ...] = (STATUS_CLEAR, *STATUS_PRECEDENCE)


def normalise_path(raw: str) -> str:
    """Put a path from a record or a diff header into one comparable form.

    ``str.lstrip`` takes a CHARACTER SET, not a prefix: ``".claude/x".lstrip("./")``
    returns ``"claude/x"``. Using it here silently mangled every dotfile path, so
    a record naming ``.claude/commands/plan.md`` could never match a diff that
    touched exactly that file and was reported PHANTOM — a blocking, false
    refutation of a true record, on the very tree (``.claude/``) where these
    records matter most. Both the record side and the diff side call this, so the
    two can only disagree about a path if they really do.

    Args:
        raw: A path as written in a record's ``Files`` field or a diff header.

    Returns:
        The path with surrounding whitespace/backticks removed, backslashes
        turned into forward slashes, and any leading ``./`` segments dropped.
    """
    path = raw.strip().strip("`").strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path


def _hunk_counts(header: str) -> tuple[int, int] | None:
    """Read how many old/new lines a ``@@`` hunk header promises.

    The counts are what tells the parser where a hunk ENDS, which is the only way to know that a
    payload line beginning ``+++ `` or ``--- `` is content rather than a file header.

    Args:
        header: A line beginning with ``@@``.

    Returns:
        ``(old_count, new_count)``, defaulting either to 1 when the header omits it (git writes
        ``@@ -3 +3 @@`` for a single-line side), or None when the header is not readable — in
        which case the caller falls back to the permissive, header-free reading.
    """
    match = _HUNK_RE.match(header)
    if match is None:
        return None
    old = int(match.group(1)) if match.group(1) is not None else 1
    new = int(match.group(2)) if match.group(2) is not None else 1
    return old, new


class InstrumentFailureError(Exception):
    """Raised when the checker cannot read its own evidence.

    Distinct from a verification failure on purpose: a caller that treats an
    unreadable diff as "nothing to report" has silently deleted the check.
    """


@dataclass
class Record:
    """One ``## Path Not Taken`` block lifted out of a Layer 1 event."""

    fields: dict[str, str]
    source: str

    @property
    def files(self) -> list[str]:
        """Repo-relative paths this record claims its decision lands in."""
        raw = self.fields.get("files", "")
        return [normalise_path(p) for p in raw.split(",") if p.strip()]

    @property
    def falsifier(self) -> str:
        """The literal that would appear in the diff if the rejected path shipped."""
        return self.fields.get("falsifier", "").strip().strip("`")

    @property
    def decision(self) -> str:
        """One-line statement of what was being decided."""
        return self.fields.get("decision", "")


@dataclass
class DiffFacts:
    """What the checker learned from the unified diff."""

    added_by_file: dict[str, list[str]] = field(default_factory=dict)
    changed_lines: dict[str, int] = field(default_factory=dict)

    @property
    def files(self) -> set[str]:
        """Every path the diff touches."""
        return set(self.changed_lines)


@dataclass
class Problem:
    """A single verification failure, ready to print or serialise."""

    kind: str
    detail: str
    source: str

    def as_dict(self) -> dict[str, str]:
        """JSON-serialisable form."""
        return {"kind": self.kind, "detail": self.detail, "source": self.source}


def _read_json_lines(path: Path) -> list[dict[str, object]]:
    """Parse an ``events.jsonl`` file into a list of event dicts.

    Args:
        path: Path to the events file.

    Returns:
        One dict per non-blank line.

    Raises:
        InstrumentFailureError: The file is missing, unreadable, or holds a line that
            is not JSON. A malformed Layer 1 file is an instrument problem, not
            an empty result.
    """
    if not path.exists():
        raise InstrumentFailureError(f"events file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InstrumentFailureError(f"cannot read events file {path}: {exc}") from exc
    events: list[dict[str, object]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as exc:
            raise InstrumentFailureError(f"{path}:{line_no} is not valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise InstrumentFailureError(f"{path}:{line_no} is not a JSON object")
        events.append(parsed)
    return events


def resolve_discussion_events(discussion_id: str) -> Path:
    """Find the ``events.jsonl`` for a discussion id.

    Args:
        discussion_id: The discussion whose events should be read.

    Returns:
        Path to that discussion's events file.

    Raises:
        InstrumentFailureError: No such discussion directory exists.
    """
    if not DISCUSSIONS_DIR.exists():
        raise InstrumentFailureError(f"no discussions directory at {DISCUSSIONS_DIR}")
    for date_dir in sorted(DISCUSSIONS_DIR.iterdir(), reverse=True):
        if not date_dir.is_dir() or date_dir.name.startswith("."):
            continue
        candidate = date_dir / discussion_id / "events.jsonl"
        if candidate.exists():
            return candidate
    raise InstrumentFailureError(f"discussion not found: {discussion_id}")


def find_record_sources(root: Path | None = None) -> list[tuple[str, str, int]]:
    """List every discussion that actually holds ``path-not-taken`` records.

    This exists because the mechanism had no working ENTRY POINT. ``/review`` needs the
    ``/plan`` and ``/build_module`` discussion ids to check anything, nothing in the workflow
    handed them over, and the documented fallback (``verifier_exit_code: NOT RUN``) was
    therefore the frictionless path for every build-driven review — i.e. the check would have
    quietly become prose while still reading as a mechanism.

    Deliberately a LISTING and not an auto-select: checking every discussion ever written
    against today's diff would report old, truthful records as PHANTOM, which is a blocking
    verdict against honest work and the one failure mode this instrument must not have. The
    caller picks the ids belonging to the change under review; this only removes the excuse
    that they could not be found.

    Args:
        root: Directory holding dated discussion folders. Defaults to
            :data:`DISCUSSIONS_DIR`; tests point it at ``tmp_path``.

    Returns:
        ``(date_dir, discussion_id, record_count)`` for each discussion holding at least one
        record, newest date first. Unreadable or malformed events files are skipped rather
        than raising: a listing that dies on one corrupt old discussion helps nobody, and the
        real verification pass over a chosen id still raises
        :class:`InstrumentFailureError`.
    """
    base = DISCUSSIONS_DIR if root is None else root
    if not base.exists():
        return []
    found: list[tuple[str, str, int]] = []
    for events in sorted(base.glob("*/*/events.jsonl")):
        try:
            count = len(collect_records(_read_json_lines(events)))
        except InstrumentFailureError:
            continue
        if count:
            found.append((events.parent.parent.name, events.parent.name, count))
    return sorted(found, reverse=True)


def parse_records(content: str, source: str) -> list[Record]:
    """Lift every ``## Path Not Taken`` block out of one event's content.

    A block runs from its heading to the next markdown heading or the end of the
    content. Fields are ``- **Name**: value`` lines; names are lowercased so the
    writer's capitalisation is not load-bearing.

    Args:
        content: The event's content string.
        source: Human-readable origin, used in problem messages.

    Returns:
        One :class:`Record` per block found, including malformed ones — a block
        missing a field must reach the checker to be reported, not be dropped
        here and silently reduce the record count.
    """
    records: list[Record] = []
    lines = content.splitlines()
    starts = [i for i, line in enumerate(lines) if line.strip() == RECORD_HEADING]
    for index, start in enumerate(starts):
        end = len(lines)
        for j in range(start + 1, len(lines)):
            if lines[j].startswith("#"):
                end = j
                break
        fields: dict[str, str] = {}
        for line in lines[start + 1 : end]:
            stripped = line.strip()
            if not stripped.startswith("- **"):
                continue
            head, _, tail = stripped[4:].partition("**:")
            if not _:
                continue
            fields[head.strip().lower()] = tail.strip()
        records.append(Record(fields=fields, source=f"{source} block {index + 1}"))
    return records


def collect_records(events: list[dict[str, object]]) -> list[Record]:
    """Gather records from every event tagged :data:`RECORD_TAG`.

    Args:
        events: Parsed Layer 1 events.

    Returns:
        Every record carried by a tagged event, in event order.
    """
    records: list[Record] = []
    for event in events:
        tags = event.get("tags") or []
        if not isinstance(tags, list) or RECORD_TAG not in tags:
            continue
        content = event.get("content")
        if not isinstance(content, str):
            continue
        turn = event.get("turn_id", "?")
        records.extend(parse_records(content, source=f"turn {turn}"))
    return records


def parse_diff(diff_text: str) -> DiffFacts:
    """Read a unified diff into per-file added lines and churn counts.

    Args:
        diff_text: Output of ``git diff`` (any base), or an equivalent unified
            diff.

    Returns:
        The added lines and total changed-line count for each touched path. A
        DELETED file (``+++ /dev/null``) is attributed to the path in its
        ``--- a/<path>`` header, with zero added lines: "delete it rather than
        keep a shim" is a recordable decision, and before this the whole file was
        invisible — a deletion-only diff raised InstrumentFailureError and halted
        the review, and a record naming the deleted file was reported PHANTOM.

    Raises:
        InstrumentFailureError: The text contains ``+``/``-`` payload lines but no
            file header at all — that is a diff the parser did not understand,
            and reporting "0 files changed" for it would be a silent pass.
    """
    facts = DiffFacts()
    current: str | None = None
    removed_source: str | None = None
    saw_payload = False
    old_left = 0
    new_left = 0

    def _register(path: str) -> str:
        facts.added_by_file.setdefault(path, [])
        facts.changed_lines.setdefault(path, 0)
        return path

    def _header_path(raw: str) -> str | None:
        target = raw.strip()
        if target == "/dev/null":
            return None
        return normalise_path(target[2:] if target.startswith(("a/", "b/")) else target)

    def _add(line: str) -> None:
        nonlocal saw_payload
        saw_payload = True
        if current is not None:
            facts.added_by_file[current].append(line[1:])
            facts.changed_lines[current] += 1

    def _remove() -> None:
        nonlocal saw_payload
        saw_payload = True
        if current is not None:
            facts.changed_lines[current] += 1

    for line in diff_text.splitlines():
        in_hunk = old_left > 0 or new_left > 0
        if in_hunk and not line.startswith("diff --git "):
            # INSIDE a hunk, a '+++ '/'--- ' line is CONTENT, never a header. Measured with real
            # git: removing `-- old sql comment` and adding `++ new marker line` in one markdown
            # file emits payload lines `--- old sql comment` and `+++ new marker line`; read as
            # headers they cost that file both of its changed lines (churn 0, so it silently
            # drops out of the coverage proxy) and registered a phantom path 'new marker line'.
            # `-- ` lines are live in this repo's own markdown (SQL examples in skill files).
            if line.startswith("\\"):  # "\ No newline at end of file" counts toward neither side
                continue
            if line.startswith("+"):
                _add(line)
                new_left = max(0, new_left - 1)
            elif line.startswith("-"):
                _remove()
                old_left = max(0, old_left - 1)
            else:
                old_left = max(0, old_left - 1)
                new_left = max(0, new_left - 1)
            continue
        old_left = new_left = 0
        if line.startswith("+++ "):
            # On a deletion the only path this hunk names is on the '---' side.
            target = _header_path(line[4:]) or removed_source
            current = _register(target) if target else None
            continue
        if line.startswith("--- "):
            removed_source = _header_path(line[4:])
            continue
        if line.startswith("@@"):
            counts = _hunk_counts(line)
            if counts is not None:
                old_left, new_left = counts
            continue
        if line.startswith("diff --git "):
            continue
        # Outside any hunk we stay permissive: a +/- line with no readable `@@` header before it
        # is still payload for the current file. That keeps a hand-written or miscounted diff
        # readable rather than silently dropping it.
        if line.startswith("+"):
            _add(line)
        elif line.startswith("-"):
            _remove()
    if saw_payload and not facts.changed_lines:
        raise InstrumentFailureError(
            "diff contains +/- lines but no '+++ <path>' header was found; "
            "the parser did not understand this diff. Pass unified `git diff` output."
        )
    return facts


def _structural_problems(record: Record) -> list[Problem]:
    """Report a record nobody could ever check (case 2).

    Args:
        record: The record to inspect.

    Returns:
        Zero or more UNFALSIFIABLE problems.
    """
    problems: list[Problem] = []
    for name in REQUIRED_FIELDS:
        value = record.fields.get(name, "").strip()
        if not value:
            problems.append(
                Problem(
                    "UNFALSIFIABLE",
                    f"required field '{name}' is missing or blank",
                    record.source,
                )
            )
    if problems:
        return problems
    if not any("/" in p or "." in p for p in record.files):
        problems.append(
            Problem(
                "UNFALSIFIABLE",
                f"'Files' names no path-shaped entry: {record.fields.get('files')!r}",
                record.source,
            )
        )
    falsifier = record.falsifier
    if len(falsifier) < MIN_FALSIFIER_LENGTH:
        problems.append(
            Problem(
                "UNFALSIFIABLE",
                f"'Falsifier' {falsifier!r} is shorter than {MIN_FALSIFIER_LENGTH} characters; "
                "it cannot identify the rejected approach in a diff",
                record.source,
            )
        )
    elif falsifier.lower() in VAGUE_FALSIFIERS:
        problems.append(
            Problem(
                "UNFALSIFIABLE",
                f"'Falsifier' {falsifier!r} names no checkable literal -- state the token, "
                "symbol, or flag that WOULD appear in the added lines if the rejected "
                "approach had shipped",
                record.source,
            )
        )
    return problems


def is_prose_line(path: str, added: str) -> bool:
    """Say whether an added line is prose rather than code taking an approach.

    A bare substring test makes the commonest honest artifact — a comment saying
    *why* an approach was rejected — refute the record of that rejection. This
    function is what keeps that from being blocking.

    Args:
        path: The file the line was added to.
        added: The added line, without its leading ``+``.

    Returns:
        True if the line is a comment or lives in a prose file.
    """
    if path.lower().endswith(PROSE_SUFFIXES):
        return True
    return added.strip().startswith(COMMENT_PREFIXES)


def _diff_problems(record: Record, facts: DiffFacts) -> list[Problem]:
    """Report a record the diff contradicts (case 1) or does not locate (PHANTOM).

    Args:
        record: A structurally valid record.
        facts: What the diff says.

    Returns:
        Zero or more CONTRADICTED / CONTRADICTED-IN-PROSE / PHANTOM problems.
    """
    problems: list[Problem] = []
    named = [p for p in record.files if p in facts.files]
    if not named:
        on_disk = [p for p in record.files if (PROJECT_ROOT / p).exists() or Path(p).exists()]
        hint = ""
        if on_disk:
            hint = (
                f" -- BUT {', '.join(on_disk)} exists on disk. If it is a NEW file, your diff "
                "omits it: `git diff` never shows untracked files. Re-take the diff after "
                "`git add --intent-to-add --all` (which stages no content) before treating "
                "this as a false record"
            )
        problems.append(
            Problem(
                "PHANTOM",
                f"'Files' ({', '.join(record.files)}) names nothing this diff touched; "
                f"the decision did not land here{hint}",
                record.source,
            )
        )
        return problems
    falsifier = record.falsifier
    for path in named:
        hits = [line for line in facts.added_by_file.get(path, []) if falsifier in line]
        # A code hit outranks a prose hit in the SAME file: scanning all hits rather
        # than breaking on the first stops a comment above the offending line from
        # downgrading a real refutation to an advisory.
        code_hits = [line for line in hits if not is_prose_line(path, line)]
        if code_hits:
            problems.append(
                Problem(
                    "CONTRADICTED",
                    f"{path} ADDS a line containing the falsifier {falsifier!r} "
                    f"({code_hits[0].strip()!r}) -- the diff took the approach this record "
                    f"claims was rejected: {record.decision!r}",
                    record.source,
                )
            )
        elif hits:
            problems.append(
                Problem(
                    "CONTRADICTED-IN-PROSE",
                    f"{path} adds a PROSE line naming the falsifier {falsifier!r} "
                    f"({hits[0].strip()!r}). Advisory, not a refutation: a comment or doc line "
                    "that discusses the rejected approach is not the code taking it. A reader "
                    "must decide whether the approach also shipped",
                    record.source,
                )
            )
    return problems


def record_status(problems: list[Problem]) -> str:
    """Collapse one record's problems into the single status the hand-off promises.

    ``/review`` Step 7 requires every claim in the hand-off block to be tagged with one
    of :data:`RECORD_STATUSES`. Before this existed the result carried only a flat
    ``problems`` list, so the command promised a per-record status that the script had
    no way to supply and the briefing agent had to reconstruct by matching problem
    ``source`` strings back to records by eye.

    Args:
        problems: Every problem raised against ONE record.

    Returns:
        The worst kind present, per :data:`STATUS_PRECEDENCE`, or
        :data:`STATUS_CLEAR` when the record drew nothing. Worst-first matters: a
        record can be CONTRADICTED in one file and only CONTRADICTED-IN-PROSE in
        another, and reporting the advisory would hide the refutation.
    """
    kinds = {problem.kind for problem in problems}
    for kind in STATUS_PRECEDENCE:
        if kind in kinds:
            return kind
    return STATUS_CLEAR


def _coverage_problems(
    records: list[Record],
    facts: DiffFacts,
    min_changed_lines: int,
    excludes: list[str],
) -> tuple[list[Problem], int, int]:
    """Report changed files no record speaks for (case 3 — a proxy, not a detector).

    Args:
        records: Every record found.
        facts: What the diff says.
        min_changed_lines: Churn at or above which a file must be spoken for.
        excludes: fnmatch globs to skip. See :data:`DEFAULT_EXCLUDES`.

    Returns:
        The UNRECORDED problems, how many files qualified for the check at all —
        printed so a vacuous pass is visible — and how many high-churn files the
        globs SKIPPED. The third number is reported rather than kept internal on
        purpose: a default exclusion nobody can see is indistinguishable from a
        proxy that silently stopped looking.
    """
    spoken_for = {p for record in records for p in record.files}
    problems: list[Problem] = []
    qualifying = 0
    excluded = 0
    for path, churn in sorted(facts.changed_lines.items()):
        if churn < min_changed_lines:
            continue
        if any(fnmatch.fnmatch(path, pattern) for pattern in excludes):
            excluded += 1
            continue
        qualifying += 1
        if path not in spoken_for:
            problems.append(
                Problem(
                    "UNRECORDED",
                    f"{path} changed {churn} lines and no record names it "
                    "(coverage proxy: this flags files, not decisions)",
                    "diff",
                )
            )
    return problems, qualifying, excluded


def verify(
    events_paths: Path | list[Path],
    diff_text: str,
    min_changed_lines: int = DEFAULT_MIN_CHANGED_LINES,
    excludes: list[str] | None = None,
) -> dict[str, object]:
    """Run every check and return a structured result.

    Args:
        events_paths: One Layer 1 ``events.jsonl``, or several. Several is the
            normal case for a spec-driven change: ``/plan`` records the design
            alternatives in its own discussion and ``/build_module`` records the
            implementation ones in another, and both sets are claims about the
            same diff.
        diff_text: Unified diff of the change under review.
        min_changed_lines: Churn threshold for the coverage proxy.
        excludes: fnmatch globs excluded from the coverage proxy. ``None`` (the
            default) means :data:`DEFAULT_EXCLUDES`; an EMPTY list means exclude
            nothing. The two are kept distinct so "I did not pass excludes" and
            "I deliberately want none" cannot be confused — the old ``or []``
            spelling collapsed them and made the default impossible to opt out of.

    Returns:
        A dict with ``exit_code``, ``records``, ``qualifying_files``,
        ``excluded_files``, and the list of ``problems``.

    Raises:
        InstrumentFailureError: Evidence could not be read or parsed.
    """
    paths = [events_paths] if isinstance(events_paths, Path) else list(events_paths)
    records: list[Record] = []
    for path in paths:
        origin = path.parent.name or path.name
        for record in collect_records(_read_json_lines(path)):
            record.source = f"{origin} {record.source}"
            records.append(record)
    facts = parse_diff(diff_text)

    problems: list[Problem] = []
    statuses: list[dict[str, str]] = []
    for record in records:
        structural = _structural_problems(record)
        own = list(structural)
        if not structural:
            own.extend(_diff_problems(record, facts))
        problems.extend(own)
        statuses.append(
            {
                "source": record.source,
                "status": record_status(own),
                "decision": record.decision,
                "files": ", ".join(record.files),
                "falsifier": record.falsifier,
            }
        )
    coverage, qualifying, excluded = _coverage_problems(
        records,
        facts,
        min_changed_lines,
        list(DEFAULT_EXCLUDES) if excludes is None else excludes,
    )

    hard = [p for p in problems if p.kind not in ADVISORY_KINDS]
    if hard:
        exit_code = EXIT_FAILED
    elif coverage:
        exit_code = EXIT_COVERAGE_GAP
    else:
        exit_code = EXIT_OK
    return {
        "exit_code": exit_code,
        "verdict": VERDICT_WORDS[exit_code],
        # The caveat rides in the PAYLOAD, not only in the rendered text: `--json` is the
        # mode /review actually invokes, and a disclaimer only the text renderer prints is
        # absent exactly where the verdict word gets copied from.
        "caveat": CLEAR_CAVEAT if exit_code == EXIT_OK else "",
        "records": len(records),
        "record_status": statuses,
        "qualifying_files": qualifying,
        "excluded_files": excluded,
        "changed_files": len(facts.changed_lines),
        "note": VACUOUS_NOTE if (not records and not qualifying) else "",
        "problems": [p.as_dict() for p in problems + coverage],
    }


def _render(result: dict[str, object]) -> str:
    """Format a human-readable summary that never hides a vacuous pass.

    Args:
        result: Output of :func:`verify`.

    Returns:
        The text to print.
    """
    lines: list[str] = []
    statuses = result.get("record_status") or []
    assert isinstance(statuses, list)
    for entry in statuses:
        # Per-record status in the TEXT mode too, so a human run and the --json run the
        # briefing agent is handed report the same five-word vocabulary.
        lines.append(f"  [{entry['status']}] {entry['source']}: {entry['decision']}")
    problems = result["problems"]
    assert isinstance(problems, list)
    for problem in problems:
        lines.append(f"  [{problem['kind']}] {problem['source']}: {problem['detail']}")
    verdict = f"PATHS_NOT_TAKEN: {VERDICT_WORDS[int(result['exit_code'])]}"
    header = (
        f"{verdict} -- {result['records']} record(s) checked, "
        f"{result['qualifying_files']} of {result['changed_files']} changed file(s) "
        f"qualified for the coverage proxy"
    )
    if result.get("excluded_files"):
        # Printed, not silent: a default exclusion nobody can see reads exactly like a proxy
        # that quietly stopped asking. The count is what makes DEFAULT_EXCLUDES falsifiable
        # from the run itself.
        header += (
            f" ({result['excluded_files']} high-churn file(s) skipped by an exclude glob; "
            "default set: " + ", ".join(DEFAULT_EXCLUDES) + ")"
        )
    if result.get("caveat"):
        header += f"\nCAVEAT: {result['caveat']}"
    if result.get("note"):
        header += f"\nNOTE: {result['note']}"
    return "\n".join([header, *lines])


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Argument vector, defaulting to ``sys.argv[1:]``.

    Returns:
        One of :data:`EXIT_OK`, :data:`EXIT_FAILED`, :data:`EXIT_COVERAGE_GAP`,
        :data:`EXIT_INSTRUMENT_FAILURE`.
    """
    parser = argparse.ArgumentParser(
        description="Verify recorded paths-not-taken against the diff that shipped."
    )
    parser.add_argument(
        "--events",
        action="append",
        default=[],
        help="Path to a Layer 1 events.jsonl (repeatable)",
    )
    parser.add_argument(
        "--discussion",
        action="append",
        default=[],
        help="Discussion id whose events.jsonl to read (repeatable; combine the /plan "
        "discussion with the /build_module one)",
    )
    parser.add_argument(
        "--diff",
        help="Path to a unified diff, or '-' to read stdin (required unless --list-sources)",
    )
    parser.add_argument(
        "--list-sources",
        action="store_true",
        help="List every discussion holding path-not-taken records, newest first, and exit. "
        "Run this BEFORE concluding there is nothing to verify: it is the only thing that "
        "distinguishes 'no records exist' from 'nobody passed me the ids'.",
    )
    parser.add_argument(
        "--min-changed-lines",
        type=int,
        default=DEFAULT_MIN_CHANGED_LINES,
        help="Churn at which an unspoken-for file is flagged "
        f"(default {DEFAULT_MIN_CHANGED_LINES})",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="fnmatch glob excluded from the coverage proxy (repeatable). ADDS to the "
        "default set (" + ", ".join(DEFAULT_EXCLUDES) + ") rather than replacing it",
    )
    parser.add_argument(
        "--no-default-excludes",
        action="store_true",
        help="Do not apply the built-in exclude set. Use it to ask the unfiltered question "
        "('which high-churn file, of any kind, is unspoken for?'); the default set exists "
        "because that question makes exit 2 the ordinary verdict",
    )
    parser.add_argument("--json", action="store_true", help="Emit the result as JSON")
    args = parser.parse_args(argv)

    if args.list_sources:
        sources = find_record_sources()
        if not sources:
            print(
                "no discussion under discussions/ holds a single 'path-not-taken' record. "
                "'NOT RUN' is honest here -- and it is also the signal that builders have "
                "stopped recording; raise it at /retro rather than writing it every week."
            )
        else:
            print(f"{len(sources)} discussion(s) hold path-not-taken records (newest first):")
            for date_dir, discussion_id, count in sources:
                print(f"  {date_dir}  {discussion_id}  ({count} record(s))")
            print(
                "Pass the ids belonging to THIS change with --discussion. They are NOT "
                "auto-selected on purpose: checking an unrelated older discussion against "
                "this diff would report its truthful records as PHANTOM."
            )
        return EXIT_OK

    if not args.events and not args.discussion:
        parser.error("at least one of --events or --discussion is required")
    if not args.diff:
        parser.error("--diff is required (use '-' to read the diff from stdin)")

    try:
        events_paths = [Path(p) for p in args.events]
        events_paths += [resolve_discussion_events(d) for d in args.discussion]
        diff_text = (
            sys.stdin.read() if args.diff == "-" else Path(args.diff).read_text(encoding="utf-8")
        )
        base = [] if args.no_default_excludes else list(DEFAULT_EXCLUDES)
        result = verify(
            events_paths,
            diff_text,
            min_changed_lines=args.min_changed_lines,
            excludes=base + args.exclude,
        )
    except InstrumentFailureError as exc:
        print(f"INSTRUMENT FAILURE [paths-not-taken]: {exc}", file=sys.stderr)
        print(
            "This is NOT a clean run. The checker could not read its evidence; "
            "fix the input before trusting any verdict.",
            file=sys.stderr,
        )
        return EXIT_INSTRUMENT_FAILURE
    except OSError as exc:
        print(f"INSTRUMENT FAILURE [paths-not-taken]: cannot read diff: {exc}", file=sys.stderr)
        return EXIT_INSTRUMENT_FAILURE

    if args.json:
        print(json.dumps(result, indent=2))
        if result.get("caveat"):
            # Same reasoning as the vacuity note below: the exit-0 verdict is the string
            # that gets copied into a review report, so its caveat must reach a caller
            # that reads only the stream, not just one that parses the payload.
            print(f"CAVEAT [paths-not-taken]: {result['caveat']}", file=sys.stderr)
        if result.get("note"):
            # Also on stderr: the anti-vacuity note is the one sentence that stops
            # "checked nothing" reading as "verified clean", and it must not depend
            # on the caller digging it out of the payload. stderr keeps stdout
            # parseable as JSON.
            print(f"NOTE [paths-not-taken]: {result['note']}", file=sys.stderr)
    else:
        print(_render(result))
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
