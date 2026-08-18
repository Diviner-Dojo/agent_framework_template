"""A pointer is a promise that a heading exists. This file checks the promise.

SPEC-20260812-122753 (slice E) single-sources three duplicated instruction blocks in the
command chain and replaces the removed copies with **pointers** — prose of the form::

    `<repo-relative .md path>`, section `<exact heading text>`

That trade is only safe while the target heading actually exists. A pointer whose target has
been renamed is worse than the duplication it replaced: the duplicate was stale, but the
pointer is a dead end at the moment of use, and the runner who follows it finds nothing and
improvises. So the pointers are pinned here.

Two design decisions, both recorded as paths-not-taken in
``DISC-20260815-060545-build-single-source-pnt-surface``:

**The check is anchored, not a substring search.** ``heading in target_text`` would be
satisfied by any echo of the heading's words anywhere in the file — a cross-reference, a
sentence quoting it, this file's own prose. ``tests/test_education_gate.py`` carries three
recorded green-under-mutation escapes of exactly that shape, which is why R5 specifies
``^#{1,6} <exact text>$`` against a line start. :meth:`TestPointerTargetsExist.
test_renaming_only_the_heading_line_turns_this_red` runs the mutation that proves it: it
renames the heading LINE while deliberately leaving an echo of its text elsewhere in the same
file, and requires this suite to go red anyway.

**Pointers are discovered by scanning, not listed in a table here.** A hand-maintained table
would be a fourth copy of the thing the slice exists to stop duplicating, and it fails
silently: a pointer added later is simply absent from it, so the run is green over an
unchecked pointer. The scan covers any pointer written in the house grammar above the moment
it is written.

The honest limit of that choice, stated rather than discovered later: **a pointer phrased
outside the grammar is invisible to this scan.** ``walkthrough.md`` Step 2a, for instance,
carries an older cross-reference in a different shape (``*The briefing agent's verification
obligation (contract)*``, emphasis rather than code markers) and is NOT counted below. That
is why :data:`POINTER_FLOOR` exists — an empty or shrunken scan fails instead of passing
quietly, which is the failure direction a scan-based check is otherwise prone to.

Read-only. Nothing here writes anything.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The command files slice E edits. Pointers are scanned from these.
POINTER_SOURCES = (
    ".claude/commands/review.md",
    ".claude/commands/walkthrough.md",
    ".claude/commands/build_module.md",
)

#: The house pointer grammar: a backticked ``.md`` path, ``, section ``, a backticked heading.
POINTER_RE = re.compile(r"`([^`\n]+\.md)`,\s+section\s+`([^`\n]+)`")

#: A ``<placeholder>`` in a pointer's target path. ``/review`` Step 10 legitimately points at
#: ``docs/reviews/REV-<ts>.md`` — a file the command itself will create later, named by a
#: timestamp that does not exist at test time. Such a pointer cannot be resolved and is
#: excluded, but it is excluded LOUDLY: :meth:`TestPointerTargetsExist.
#: test_templated_pointers_are_excluded_visibly` prints the census, so converting a resolvable
#: pointer into a templated one shows up as a change in that count rather than as a silent
#: drop out of coverage. Found by this scan on its first run, not predicted.
PLACEHOLDER_RE = re.compile(r"[<>]")

#: Minimum pointers the scan must find, set to the EXACT current resolvable count so that
#: losing any single one trips it. The enumeration, corrected after a reviewer measured it:
#: R1 contributes **two** (the rationale pointer and the reversal pointer, both into
#: ``build_module.md`` Step 6.5), R4 one (``review.md`` self-pointer), R3 one
#: (``walkthrough.md`` -> ``review.md``) = 4. An earlier revision said 3 on the arithmetic
#: "R1, R3 and R4 each add exactly one", and the one unit of slack was demonstrated live: a
#: reviewer deleted R3's entire cross-file pointer and the full suite — all 316 tests — stayed
#: green. Raise it when a slice adds more; never lower it to make a run pass.
POINTER_FLOOR = 4

#: R4's stable phrase. The Step 6.4 pointer targets this sentence rather than a list-item
#: number, because item numbering in a contract shifts whenever an obligation is inserted and
#: a pointer to "item 5" then silently addresses the wrong obligation.
STABLE_PHRASE = "MECHANICALLY-CLEAR may never be promoted to VERIFIED"

#: The subsection R4's stable phrase must live in.
CONTRACT_HEADING = "The briefing agent's verification obligation (contract)"

#: ``(target file, heading) -> a phrase that must be INSIDE that section``.
#:
#: A heading-existence check answers "is there a heading with this name", which is not the
#: promise a pointer makes. The promise is "the content is there". Measured by a blind
#: reviewer: replacing the whole body of ``build_module.md`` Step 6.5 with ``TODO: rewrite``
#: left every heading assertion green while ``review.md`` went on promising the full measured
#: rationale was in it; and deleting the ``refuted-at-gate`` capture block from the contract
#: subsection left both the heading pin AND the stable-phrase pin green while
#: ``walkthrough.md`` promised the call was specified there. Each anchor below is the content
#: a live pointer actually claims, so the claim and the check are the same statement.
CONTENT_ANCHORS: tuple[tuple[str, str, str], ...] = (
    (
        ".claude/commands/build_module.md",
        "Step 6.5: Self-Check the Path-Not-Taken Records",
        "named 14",
    ),
    (
        ".claude/commands/build_module.md",
        "Step 6.5: Self-Check the Path-Not-Taken Records",
        "git reset -q -- ",
    ),
    (".claude/commands/review.md", CONTRACT_HEADING, "refuted-at-gate"),
    (".claude/commands/review.md", CONTRACT_HEADING, STABLE_PHRASE),
)


def collapsed(text: str) -> str:
    """``text`` with line wrapping removed, so a pointer may wrap mid-phrase.

    Both prose and bash-comment wrapping are handled: a newline, any indentation, and an
    optional ``#`` comment marker collapse to a single space. Without this the scan would
    only find pointers that happen to fit on one line, and would silently under-report — the
    same wrap blindness that made the spec's own draft ``grep`` for ``named 14 paths`` return
    1 where the true count was 2.

    Args:
        text: A command file's full text.

    Returns:
        The text with every line break collapsed to a single space.
    """
    return re.sub(r"\s*\n\s*(?:#\s*)?", " ", text)


def pointers() -> list[tuple[str, str, str]]:
    """Every pointer in the house grammar across :data:`POINTER_SOURCES`.

    Returns:
        ``(source path, target path, target heading text)`` triples.
    """
    found: list[tuple[str, str, str]] = []
    for rel in POINTER_SOURCES:
        text = collapsed((REPO_ROOT / rel).read_text(encoding="utf-8"))
        for target, heading in POINTER_RE.findall(text):
            # Two citation grammars exist in this repo: slice E writes the heading bare
            # (`Step 6.5: …`) while `quiz.md` and `review.md` Step 10 keep the markers
            # (`## Paths Not Taken — Verification Handoff`). Normalising here means the
            # with-markers form resolves instead of producing "no heading line" against a
            # heading that is plainly present.
            found.append((rel, target, re.sub(r"^#{1,6}\s+", "", heading)))
    return found


def resolvable_pointers() -> list[tuple[str, str, str]]:
    """:func:`pointers`, minus the ones whose target path is a template.

    Returns:
        ``(source path, target path, target heading text)`` triples that name a concrete file.
    """
    return [p for p in pointers() if not PLACEHOLDER_RE.search(p[1])]


def templated_pointers() -> list[tuple[str, str, str]]:
    """:func:`pointers` that name a ``<placeholder>`` path and so cannot be resolved.

    Returns:
        ``(source path, target path, target heading text)`` triples with templated targets.
    """
    return [p for p in pointers() if PLACEHOLDER_RE.search(p[1])]


def norm_phrase(text: str) -> str:
    """``text`` with wrapping and markdown emphasis removed, for content comparisons.

    The pointer scan is wrap-tolerant; the content checks must be too. Measured: re-wrapping
    an unmodified sentence at a different column flipped a naive membership test to False and
    produced a failure message that sent an editor hunting for a sentence nobody had removed.
    """
    return " ".join(text.replace("`", "").replace("*", "").split())


def heading_line_exists(text: str, heading: str) -> bool:
    """Whether ``heading`` appears as a real markdown heading line in ``text``.

    Anchored at a line start and terminated at the line end, so an echo of the heading's
    words in a sentence — including a pointer to it — cannot vouch for it.

    Args:
        text: The target file's full text.
        heading: Exact heading text, without its ``#`` markers.

    Returns:
        Whether a line of the form ``#{1,6} <heading>`` exists.
    """
    return bool(re.search(rf"^#{{1,6}}\s+{re.escape(heading)}\s*$", text, flags=re.MULTILINE))


def _fence_mask(text: str) -> list[bool]:
    """Per-line flag: is this line inside a ```-fenced block?

    Needed because a bash comment at column 0 (``# MANDATORY first line…``) is
    indistinguishable from an ``h1`` heading by regex alone. A blind reviewer measured the
    consequence: :func:`subsection` on ``build_module.md`` Step 6.5 returned 194 characters of
    a multi-hundred-line section, truncating at the first unindented fence comment — and the
    truncated body silently excluded the very content a pointer promises is there.

    Args:
        text: The file's full text.

    Returns:
        One boolean per line, True when the line sits inside a fence.
    """
    inside = False
    mask: list[bool] = []
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            mask.append(True)
            inside = not inside
            continue
        mask.append(inside)
    return mask


def subsection(text: str, heading: str) -> str:
    """The body of ``heading``'s subsection, up to the next heading of any level.

    Fence-aware: a ``#`` line inside a ```-fenced block is a shell comment, not a heading, and
    does not terminate the section.

    Args:
        text: The target file's full text.
        heading: Exact heading text, without its ``#`` markers.

    Returns:
        The subsection body, or ``""`` when the heading is absent.
    """
    match = re.search(rf"^(#{{1,6}})\s+{re.escape(heading)}\s*$", text, flags=re.MULTILINE)
    if not match:
        return ""
    mask = _fence_mask(text)
    start_line = text[: match.end()].count("\n")
    lines = text.splitlines(keepends=True)
    body: list[str] = []
    for idx in range(start_line + 1, len(lines)):
        if not mask[idx] and re.match(r"^#{1,6}\s+\S", lines[idx]):
            break
        body.append(lines[idx])
    return "".join(body)


class TestPointerTargetsExist:
    """Every pointer resolves to a real heading in a real file."""

    def test_the_scan_finds_the_pointers_it_claims_to_check(self) -> None:
        """Non-vacuity. A scan-based guard that finds nothing must fail, not pass."""
        found = resolvable_pointers()
        assert len(found) >= POINTER_FLOOR, (
            f"the pointer scan found {len(found)} pointer(s) in {list(POINTER_SOURCES)}, below "
            f"the floor of {POINTER_FLOOR}. Either a pointer was removed, or one was rephrased "
            "outside the house grammar (`<path>`, section `<heading>`) and is now unchecked. "
            "Re-point this guard at the new shape rather than lowering the floor — a scan that "
            "matches nothing is green forever.\n"
            f"Found: {found}"
        )

    def test_the_cross_file_pointer_r3_added_is_specifically_present(self) -> None:
        """An aggregate floor cannot protect a specific pointer. This one names it.

        Measured by a blind reviewer: deleting R3's entire ``walkthrough.md`` -> ``review.md``
        pointer — the one cross-file edge R3 exists to create — left the full suite green,
        because the aggregate count merely dropped to the then-floor. The requirement that
        spans two files is the one most worth naming individually.
        """
        sources = {source for source, _t, _h in resolvable_pointers()}
        assert ".claude/commands/walkthrough.md" in sources, (
            "walkthrough.md no longer carries a resolvable pointer in the house grammar. R3 "
            "removed the duplicated REFUTED-consequence text from it on the promise that a "
            "pointer would carry the reader to the contract; without the pointer the text is "
            "simply gone.\n"
            f"Pointer sources found: {sorted(sources)}"
        )

    @pytest.mark.parametrize("rel", POINTER_SOURCES)
    def test_every_pointer_source_is_a_file_that_exists(self, rel: str) -> None:
        """Guards the scan's own inputs: a renamed command file must not silently empty it."""
        assert (REPO_ROOT / rel).is_file(), (
            f"{rel} is named as a pointer source but does not exist, so the scan reads nothing "
            "from it and every pointer it held is unchecked"
        )

    def test_every_pointer_resolves_to_an_anchored_heading(self) -> None:
        """The promise itself: file exists, and the heading exists AS a heading."""
        broken: list[str] = []
        for source, target, heading in resolvable_pointers():
            path = REPO_ROOT / target
            if not path.is_file():
                broken.append(f"{source} -> {target} (no such file), section {heading!r}")
                continue
            if not heading_line_exists(path.read_text(encoding="utf-8"), heading):
                broken.append(f"{source} -> {target}, no heading line {heading!r}")
        assert not broken, (
            "these pointers name a heading that is not a heading in the file they name:\n  "
            + "\n  ".join(broken)
            + "\nSlice E removed the duplicated text these point at. A dead pointer is worse "
            "than the duplicate it replaced: the reader who follows it finds nothing and "
            "improvises the instruction instead. Fix the pointer, or restore the heading."
        )

    def test_templated_pointers_are_excluded_visibly(self) -> None:
        """The exclusion is a census, not a silent drop.

        A pointer at ``docs/reviews/REV-<ts>.md`` cannot be resolved at test time — the file
        is created later, by the command doing the pointing. Excluding it is correct; excluding
        it quietly is not, because rephrasing a resolvable pointer into a templated one would
        then remove it from coverage with no signal. This test states the population instead.
        """
        templated = templated_pointers()
        for _source, target, _heading in templated:
            assert target.endswith(".md") and PLACEHOLDER_RE.search(target), (
                f"{target!r} was classified as templated but carries no placeholder; the "
                "exclusion rule has drifted and is now hiding a resolvable pointer"
            )
        assert len(templated) <= 1, (
            "more pointers are excluded as templated than this guard was written against "
            f"({len(templated)}): {templated}. Each one is a pointer nothing verifies. Confirm "
            "every entry genuinely names a file that does not exist until runtime, then raise "
            "this bound deliberately."
        )

    @pytest.mark.regression
    def test_renaming_only_the_heading_line_turns_this_red(self, tmp_path: Path) -> None:
        """The echo-proof mutation, run rather than asserted.

        R5's requirement in one executable statement: rename ONLY the heading line, leave an
        echo of its exact text elsewhere in the same file, and the check must still go red.
        A substring implementation (``heading in text``) passes this mutation, which is why
        the anchored form is specified — and why proving it needs a mutation rather than a
        reading of the assertion.
        """
        target = REPO_ROOT / ".claude/commands/build_module.md"
        heading = "Step 6.5: Self-Check the Path-Not-Taken Records"
        original = target.read_text(encoding="utf-8")
        assert heading_line_exists(original, heading), (
            "premise broken: the heading this mutation renames is already absent"
        )

        # Rename the heading LINE only, and plant an echo of the original text as ordinary
        # prose — the exact confound a substring check would be fooled by.
        mutated = re.sub(
            rf"^(#{{1,6}})\s+{re.escape(heading)}\s*$",
            r"\1 Step 6.5: Renamed By Mutation",
            original,
            flags=re.MULTILINE,
        )
        mutated += f"\n<!-- echo, not a heading: {heading} -->\n"
        assert mutated != original, "the mutation did not change the file"
        assert heading in mutated, "the mutation removed the echo it is supposed to plant"

        assert not heading_line_exists(mutated, heading), (
            "the heading-existence check is vouched for by an ECHO: the heading line was "
            "renamed and the check still reports it present. That is the substring defect R5 "
            "exists to exclude — anchor the match to a line start and a line end."
        )

        # Written under tmp_path, never over the repo file, so a failure here cannot leave the
        # live command file mutated.
        scratch = tmp_path / "mutated_build_module.md"
        scratch.write_text(mutated, encoding="utf-8")
        assert not heading_line_exists(scratch.read_text(encoding="utf-8"), heading)
        assert target.read_text(encoding="utf-8") == original, (
            "the live command file changed during the mutation test"
        )


class TestTheStablePhraseIsWhereThePointerSaysItIs:
    """R4 points at a sentence, not a list-item number. The sentence must be there."""

    def test_every_pointer_target_still_holds_its_content(self) -> None:
        """Heading existence is not the promise; content presence is."""
        missing: list[str] = []
        for rel, heading, anchor in CONTENT_ANCHORS:
            body = subsection((REPO_ROOT / rel).read_text(encoding="utf-8"), heading)
            if not body:
                missing.append(f"{rel}: section {heading!r} absent entirely")
            elif norm_phrase(anchor) not in norm_phrase(body):
                missing.append(f"{rel} § {heading!r} no longer contains {anchor!r}")
        assert not missing, (
            "a pointer's target heading still exists but the content it promises is gone:\n  "
            + "\n  ".join(missing)
            + "\nA pointer says 'the thing is over there'. When the heading survives and the "
            "content does not, every guard that checks only the heading stays green while the "
            "instruction it points at has been deleted."
        )

    def test_the_stable_phrase_is_stated_once_not_restated_beside_its_pointer(self) -> None:
        """The failure this slice committed against itself, turned into a guard.

        R4 replaces a duplicated rule with a pointer. A revision of that pointer quoted the
        rule verbatim *and* claimed it was 'stated once' — taking the count from 1 to 2 and
        making the sentence its own counter-example. The stable-phrase test could not see it:
        it asserts the phrase is IN the contract subsection, never that it is stated once.
        """
        text = (REPO_ROOT / ".claude/commands/review.md").read_text(encoding="utf-8")
        count = norm_phrase(text).count(norm_phrase(STABLE_PHRASE))
        assert count == 1, (
            f"{STABLE_PHRASE!r} appears {count} times in review.md; it must appear exactly "
            "once. A pointer that restates the rule it points at has not deduplicated "
            "anything — it has added a copy and attached a claim of singularity to it."
        )

    def test_the_stable_phrase_lives_in_the_contract_subsection(self) -> None:
        """A pointer to 'item 5' breaks silently when an obligation is inserted above it."""
        text = (REPO_ROOT / ".claude/commands/review.md").read_text(encoding="utf-8")
        body = subsection(text, CONTRACT_HEADING)
        assert body, (
            f"review.md has no section {CONTRACT_HEADING!r}. Step 6.4 and walkthrough.md Step "
            "2a both point at it for the two-vocabulary rule; without it they point at nothing."
        )
        # Code markers are presentation: the phrase is pinned by its words, so re-emphasising
        # it does not fail, while removing or reworking it does.
        assert norm_phrase(STABLE_PHRASE) in norm_phrase(body), (
            f"the contract subsection no longer states {STABLE_PHRASE!r}. That sentence is the "
            "pointer target for BOTH surfaces slice E deduplicated — review.md Step 6.4's "
            "exit-0 bullet and walkthrough.md Step 2a — so losing it leaves the rule stated "
            "nowhere while two files claim it is stated here.\n"
            f"Subsection was: {body[:400]!r}"
        )
