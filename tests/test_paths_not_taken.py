"""Guards the paths-not-taken mechanism: the instructions, and the checker they promise.

Why this file exists
--------------------
`/build_module` and `/plan` now ask a builder to record, at the moment of the choice, what it
decided against. `/review` promises the briefing agent will check those claims against the diff.
That promise is the whole point: a self-reported "alternatives considered" is exactly the artifact
that becomes a comfortable fiction, and this repo's own review record names *"performed honesty
that displaces the real check"* as a failure mode. If the checker cannot fail a claim, the
mechanism manufactured the fiction instead of catching it.

So this module tests two different things, and the second is the load-bearing one:

1. **The instructions still say what they must say.** Structural, not literal: the record step
   must sit *inside* the per-task loop (a closing summary step is a reconstruction, which is the
   defect), the six fields must exist, and the exit codes must be documented with distinct
   consequences.
2. **The checker actually fails.** Every failing arm is exercised — a record the diff refutes, a
   record about files the diff never touched, a record too vague to check, a file nobody spoke
   for, and three shapes of unreadable evidence. A checker that only has passing tests is a
   checker nobody has seen say no.

What "fails on rewordings" means here
-------------------------------------
Every claim that is stated in **more than one place** is pinned to *exact agreement between the
places*, not to the literal that happened to ship. The record heading, the six field names and
their order, the tag, the minimum falsifier length, the verdict words, and the problem-kind names
all live in ``scripts/verify_paths_not_taken.py`` **and** in the command prose. Rewording either
side alone fails, which is the drift this effort has already been bitten by three times. Where a
claim exists in only one place, the assertion is on its *structure* — position in the file, the
presence of every exit code, one consequence per code, or a **relation between two tokens inside a
window** (``REFUTED`` near "not taught", "do not trust" near "exit code") — so an author may
rewrite the prose but not delete the mechanism.

That paragraph used to claim more than the file delivered: four assertions were plain ``in``-tests
on whole sentences lifted from ``review.md``, so a benign rewording went RED with a message about
a deleted mechanism — training the next author to paste the sentence back rather than think about
the guard, which is the exact reflex this slice exists to cure. They are relations now. Two
literal-token exceptions remain **on purpose**, and they are load-bearing rather than stylistic:
the problem-kind names (``CONTRADICTED``, ``PHANTOM``, ``UNFALSIFIABLE``, ``UNRECORDED``,
``CONTRADICTED-IN-PROSE``) and the per-claim verdict words are tokens the *script* emits and the
extractor parses, so they are cross-file agreements, not prose.

Honest limits, pinned as executable tests rather than as a paragraph
--------------------------------------------------------------------
``TestTheCheckerSHonestLimits`` asserts the things the checker CANNOT do — a semantically
contradictory record with a clean falsifier passes, and a real decision inside a small hunk is
never flagged. Those tests exist so the limits cannot be quietly overstated later: if someone
claims full coverage of the three cases, one of these tests is the sentence they have to delete.

.. warning::

   **THIS GUARD DOES NOT TRAVEL WITH THE THING IT GUARDS.** Measured by reading the constant
   where it is DEFINED — ``scripts/lineage/manifest.py`` lines 21-27, which is the file to open;
   ``scripts/distribute/change_package.py`` only mentions it in a docstring — ``FRAMEWORK_PATHS``
   is ``['.claude/', 'scripts/', 'CLAUDE.md', 'docs/templates/', 'docs/adr/']``. It covers
   ``.claude/`` and ``scripts/``, so ``/apply-framework`` propagates *both* the command prose and
   ``scripts/verify_paths_not_taken.py`` into every derived project — but ``tests/`` is not in
   that set, so this module stays in the hub. A derived project therefore gets the mechanism and
   not the drift detector. Same standing limitation as ``tests/test_command_sql.py``, with the
   same two fixes (add this file to ``FRAMEWORK_PATHS``, or move the assertions into a
   ``scripts/`` module), both requiring developer sign-off. Read a green run here as evidence
   about the hub only.

Nothing here writes outside ``tmp_path``.
"""

from __future__ import annotations

import fnmatch
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(REPO_ROOT / "scripts"))

import verify_paths_not_taken as vpnt  # noqa: E402

BUILD_MODULE = REPO_ROOT / ".claude/commands/build_module.md"
PLAN = REPO_ROOT / ".claude/commands/plan.md"
REVIEW = REPO_ROOT / ".claude/commands/review.md"

#: Exit code -> the verdict word the script itself prints for it.
#:
#: This used to be four literals written HERE, and the docstring above them claimed "both sides
#: of this mapping are read from the module under test". They were not: only the keys came from
#: the module, and the words were a second copy. Measured — renaming the exit-0 verdict in the
#: script from ``VERIFIED`` to ``MECHANICALLY-CLEAR`` left all 163 tests green, so the one guard
#: that named the verdict vocabulary could not see the vocabulary change. It is now imported, so
#: a rename lands in the prose assertions that consume it instead of being absorbed here.
VERDICT_WORDS = vpnt.VERDICT_WORDS


# ---------------------------------------------------------------------------
# Fixture builders — every one writes only under tmp_path
# ---------------------------------------------------------------------------


def make_record(**overrides: str) -> str:
    """Build one ``## Path Not Taken`` block, with fields overridable per test.

    Args:
        **overrides: Field values keyed by the lowercase field name.

    Returns:
        The block as it would appear in an event's content.
    """
    fields = {
        "Decision": "how the guard rejects a bad command block",
        "Chosen": "move the check into a script",
        "Rejected": "a fourth regex patch to the command text",
        "Why rejected": "three prior rounds of patching failed",
        "Files": "scripts/guard.py",
        "Falsifier": "COMMAND_TEXT_RE",
    }
    for key, value in overrides.items():
        fields[key.replace("_", " ").title().replace("Why Rejected", "Why rejected")] = value
    lines = [vpnt.RECORD_HEADING]
    lines += [f"- **{name}**: {value}" for name, value in fields.items()]
    return "\n".join(lines) + "\n"


def write_events(tmp_path: Path, *contents: str, tag: str | None = None) -> Path:
    """Write an ``events.jsonl`` holding one tagged event per content string.

    Args:
        tmp_path: The test's temp directory.
        *contents: Event content strings.
        tag: Tag to attach; defaults to the module's record tag.

    Returns:
        Path to the written events file.
    """
    path = tmp_path / "events.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for turn, content in enumerate(contents, start=1):
            handle.write(
                json.dumps(
                    {
                        "discussion_id": "DISC-test",
                        "turn_id": turn,
                        "agent": "facilitator",
                        "intent": "decision",
                        "content": content,
                        "tags": [tag or vpnt.RECORD_TAG],
                        "confidence": 0.8,
                        "risk_flags": [],
                    }
                )
                + "\n"
            )
    return path


def make_diff(path: str, added: list[str], removed: list[str] | None = None) -> str:
    """Build a unified diff touching one file.

    Args:
        path: Repo-relative path of the changed file.
        added: Lines the diff adds (without the leading ``+``).
        removed: Lines the diff removes.

    Returns:
        Unified diff text.
    """
    body = [f"diff --git a/{path} b/{path}", f"--- a/{path}", f"+++ b/{path}", "@@ -1,1 +1,1 @@"]
    body += [f"-{line}" for line in removed or []]
    body += [f"+{line}" for line in added]
    return "\n".join(body) + "\n"


def kinds(result: dict[str, object]) -> list[str]:
    """Extract the problem kinds from a :func:`verify_paths_not_taken.verify` result.

    Args:
        result: The verify() return value.

    Returns:
        Every problem kind, in report order.
    """
    problems = result["problems"]
    assert isinstance(problems, list)
    return [p["kind"] for p in problems]


# ---------------------------------------------------------------------------
# 1. The checker says YES when it should
# ---------------------------------------------------------------------------


class TestTheCheckerPasses:
    """A record whose claim the diff supports must not be flagged."""

    def test_a_true_record_verifies(self, tmp_path: Path) -> None:
        """The falsifier is absent from the added lines, so the claim stands."""
        events = write_events(tmp_path, make_record())
        diff = make_diff("scripts/guard.py", ["def check(path):", "    return run_script(path)"])
        result = vpnt.verify(events, diff)
        assert result["exit_code"] == vpnt.EXIT_OK, result["problems"]
        assert result["records"] == 1

    def test_records_from_several_discussions_combine(self, tmp_path: Path) -> None:
        """A spec-driven change has /plan records and /build_module records about one diff."""
        plan_dir = tmp_path / "plan"
        build_dir = tmp_path / "build"
        plan_dir.mkdir()
        build_dir.mkdir()
        a = write_events(plan_dir, make_record(Decision="spec-time choice"))
        b = write_events(build_dir, make_record(Decision="build-time choice"))
        diff = make_diff("scripts/guard.py", ["def check(path): ..."])
        result = vpnt.verify([a, b], diff)
        assert result["records"] == 2, "records from a second discussion were dropped"
        assert result["exit_code"] == vpnt.EXIT_OK

    def test_untagged_events_are_not_records(self, tmp_path: Path) -> None:
        """Reading by tag is the contract; an untagged block must not count as a record."""
        events = write_events(tmp_path, make_record(), tag="checkpoint")
        result = vpnt.verify(events, make_diff("scripts/guard.py", ["x = 1"]))
        assert result["records"] == 0

    def test_a_falsifier_in_a_file_the_record_does_not_claim_is_not_a_contradiction(
        self, tmp_path: Path
    ) -> None:
        """Scoping matters: an unrelated file using the same token must not refute the claim."""
        events = write_events(tmp_path, make_record())
        diff = make_diff("scripts/guard.py", ["def check(): ..."]) + make_diff(
            "scripts/other.py", ["COMMAND_TEXT_RE = 1"]
        )
        result = vpnt.verify(events, diff, min_changed_lines=999)
        assert "CONTRADICTED" not in kinds(result), (
            "the falsifier was matched outside the record's own files, which would make every "
            "shared token a false refutation and teach people to stop recording"
        )


# ---------------------------------------------------------------------------
# 2. The checker says NO when it must — the arms that matter
# ---------------------------------------------------------------------------


class TestTheCheckerFails:
    """Every failing arm. A checker with only passing tests has never been seen to say no."""

    def test_case_1_the_diff_contradicts_the_claim(self, tmp_path: Path) -> None:
        """The 'rejected' approach is what shipped: the falsifier is in the added lines."""
        events = write_events(tmp_path, make_record())
        diff = make_diff("scripts/guard.py", ["COMMAND_TEXT_RE = re.compile(r'x')"])
        result = vpnt.verify(events, diff)
        assert result["exit_code"] == vpnt.EXIT_FAILED
        assert "CONTRADICTED" in kinds(result)

    def test_a_record_about_files_the_diff_never_touched_is_phantom(self, tmp_path: Path) -> None:
        """A decision that did not land here is a claim the diff denies by omission."""
        events = write_events(tmp_path, make_record(Files="src/nowhere.py"))
        result = vpnt.verify(events, make_diff("scripts/guard.py", ["x = 1"]))
        assert result["exit_code"] == vpnt.EXIT_FAILED
        assert "PHANTOM" in kinds(result)

    @pytest.mark.parametrize("field", vpnt.REQUIRED_FIELDS)
    def test_case_2_every_required_field_is_actually_required(
        self, tmp_path: Path, field: str
    ) -> None:
        """Dropping any one field must fail — a partial record is not a checkable one."""
        block = make_record()
        stripped = "\n".join(
            line
            for line in block.splitlines()
            if not line.lower().startswith(f"- **{field}**:".lower())
        )
        events = write_events(tmp_path, stripped + "\n")
        result = vpnt.verify(events, make_diff("scripts/guard.py", ["x = 1"]))
        assert result["exit_code"] == vpnt.EXIT_FAILED, f"missing '{field}' was accepted"
        assert "UNFALSIFIABLE" in kinds(result)

    @pytest.mark.parametrize("vague", sorted(vpnt.VAGUE_FALSIFIERS))
    def test_case_2_a_vague_falsifier_is_rejected(self, tmp_path: Path, vague: str) -> None:
        """Every entry in the vague list must really be refused, in any capitalisation."""
        events = write_events(tmp_path, make_record(Falsifier=vague.upper()))
        result = vpnt.verify(events, make_diff("scripts/guard.py", ["x = 1"]))
        assert result["exit_code"] == vpnt.EXIT_FAILED, f"{vague!r} passed as a falsifier"
        assert "UNFALSIFIABLE" in kinds(result)

    def test_case_2_a_too_short_falsifier_is_rejected(self, tmp_path: Path) -> None:
        """A token shorter than the floor matches half a codebase and checks nothing."""
        short = "x" * (vpnt.MIN_FALSIFIER_LENGTH - 1)
        events = write_events(tmp_path, make_record(Falsifier=short))
        result = vpnt.verify(events, make_diff("scripts/guard.py", ["y = 1"]))
        assert result["exit_code"] == vpnt.EXIT_FAILED
        assert "UNFALSIFIABLE" in kinds(result)

    def test_case_2_files_with_nothing_path_shaped_is_rejected(self, tmp_path: Path) -> None:
        """'the usual places' is not a location a diff can be compared against."""
        events = write_events(tmp_path, make_record(Files="the usual places"))
        result = vpnt.verify(events, make_diff("scripts/guard.py", ["x = 1"]))
        assert result["exit_code"] == vpnt.EXIT_FAILED
        assert "UNFALSIFIABLE" in kinds(result)

    def test_case_3_a_changed_file_nobody_spoke_for_is_reported(self, tmp_path: Path) -> None:
        """The silent case, as far as a file-level proxy can reach it."""
        events = write_events(tmp_path, make_record())
        diff = make_diff("scripts/guard.py", ["ok = 1"]) + make_diff(
            "src/silent.py", [f"line{i}" for i in range(30)]
        )
        result = vpnt.verify(events, diff, min_changed_lines=20)
        assert result["exit_code"] == vpnt.EXIT_COVERAGE_GAP
        assert kinds(result) == ["UNRECORDED"]

    def test_a_hard_failure_outranks_a_coverage_gap(self, tmp_path: Path) -> None:
        """Exit 2 must never mask an exit-1 condition present in the same run."""
        events = write_events(tmp_path, make_record())
        diff = make_diff("scripts/guard.py", ["COMMAND_TEXT_RE = 1"]) + make_diff(
            "src/silent.py", [f"line{i}" for i in range(30)]
        )
        result = vpnt.verify(events, diff, min_changed_lines=20)
        assert result["exit_code"] == vpnt.EXIT_FAILED
        assert {"CONTRADICTED", "UNRECORDED"} <= set(kinds(result))


# ---------------------------------------------------------------------------
# 3. Unreadable evidence is never a pass
# ---------------------------------------------------------------------------


class TestInstrumentFailureIsNeverSilence:
    """A verifier that cannot read its evidence must not report 'clean'."""

    def test_missing_events_file_raises(self, tmp_path: Path) -> None:
        """Absent Layer 1 is an instrument problem, not an empty result."""
        with pytest.raises(vpnt.InstrumentFailureError):
            vpnt.verify(tmp_path / "nope.jsonl", make_diff("a.py", ["x = 1"]))

    def test_malformed_events_line_raises(self, tmp_path: Path) -> None:
        """A corrupt events line must stop the run, not silently drop the record."""
        path = tmp_path / "events.jsonl"
        path.write_text('{"turn_id": 1, "tags": ["path-not-taken"]\n', encoding="utf-8")
        with pytest.raises(vpnt.InstrumentFailureError):
            vpnt.verify(path, make_diff("a.py", ["x = 1"]))

    def test_an_unparsed_diff_raises_rather_than_reporting_zero_files(
        self, tmp_path: Path
    ) -> None:
        """+/- payload with no file header means the parser did not understand the diff."""
        events = write_events(tmp_path, make_record())
        with pytest.raises(vpnt.InstrumentFailureError):
            vpnt.verify(events, "+added a line\n-removed a line\n")

    def test_a_vacuous_run_says_so_in_words(self, tmp_path: Path) -> None:
        """Zero records over zero qualifying files must not read like a clean bill of health."""
        events = write_events(tmp_path, "no blocks here", tag=vpnt.RECORD_TAG)
        result = vpnt.verify(events, make_diff("a.py", ["x = 1"]), min_changed_lines=999)
        assert result["exit_code"] == vpnt.EXIT_OK
        rendered = vpnt._render(result)
        assert "asserted almost nothing" in rendered, (
            "a run that checked nothing printed a bare pass; that is the sentence that turns an "
            "unrun check into a passed one"
        )


# ---------------------------------------------------------------------------
# 4. The CLI contract — exit codes a caller branches on
# ---------------------------------------------------------------------------


class TestCliExitCodes:
    """The commands branch on these numbers. Measured through a real subprocess."""

    def _run(self, tmp_path: Path, events: Path, diff_text: str, *extra: str) -> tuple[int, str]:
        diff_path = tmp_path / "change.diff"
        diff_path.write_text(diff_text, encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/verify_paths_not_taken.py"),
                "--events",
                str(events),
                "--diff",
                str(diff_path),
                *extra,
            ],
            capture_output=True,
            text=True,
            cwd=tmp_path,
        )
        return proc.returncode, proc.stdout + proc.stderr

    def test_clean_run_exits_zero(self, tmp_path: Path) -> None:
        """Exit 0 is reachable — otherwise every other arm proves nothing."""
        events = write_events(tmp_path, make_record())
        code, out = self._run(tmp_path, events, make_diff("scripts/guard.py", ["ok = 1"]))
        assert code == vpnt.EXIT_OK, out
        assert VERDICT_WORDS[vpnt.EXIT_OK] in out

    def test_refuted_run_exits_one(self, tmp_path: Path) -> None:
        """The failing arm, through the real entry point."""
        events = write_events(tmp_path, make_record())
        code, out = self._run(
            tmp_path, events, make_diff("scripts/guard.py", ["COMMAND_TEXT_RE = 1"])
        )
        assert code == vpnt.EXIT_FAILED, out
        assert "CONTRADICTED" in out

    def test_coverage_gap_exits_two(self, tmp_path: Path) -> None:
        """Exit 2 is distinct from exit 1 — collapsing them deletes the distinction."""
        events = write_events(tmp_path, make_record())
        diff = make_diff("scripts/guard.py", ["ok = 1"]) + make_diff(
            "src/silent.py", [f"line{i}" for i in range(30)]
        )
        code, out = self._run(tmp_path, events, diff)
        assert code == vpnt.EXIT_COVERAGE_GAP, out

    def test_unreadable_evidence_exits_three(self, tmp_path: Path) -> None:
        """Exit 3 must be its own code; 0 here would be the defect the mechanism targets."""
        code, out = self._run(tmp_path, tmp_path / "absent.jsonl", make_diff("a.py", ["x = 1"]))
        assert code == vpnt.EXIT_INSTRUMENT_FAILURE, out
        assert VERDICT_WORDS[vpnt.EXIT_INSTRUMENT_FAILURE] in out

    def test_no_source_argument_is_an_error_not_a_pass(self, tmp_path: Path) -> None:
        """Forgetting --events/--discussion must not produce a green run over zero records."""
        diff_path = tmp_path / "c.diff"
        diff_path.write_text(make_diff("a.py", ["x = 1"]), encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/verify_paths_not_taken.py"),
                "--diff",
                str(diff_path),
            ],
            capture_output=True,
            text=True,
            cwd=tmp_path,
        )
        assert proc.returncode != vpnt.EXIT_OK

    def test_json_mode_carries_the_exit_code_it_returned(self, tmp_path: Path) -> None:
        """The commands parse --json; the payload must agree with the process exit code."""
        events = write_events(tmp_path, make_record())
        code, out = self._run(
            tmp_path, events, make_diff("scripts/guard.py", ["COMMAND_TEXT_RE = 1"]), "--json"
        )
        payload = json.loads(out)
        assert payload["exit_code"] == code == vpnt.EXIT_FAILED


# ---------------------------------------------------------------------------
# 5. Real git output, not only hand-written diffs
# ---------------------------------------------------------------------------


class TestAgainstRealGitOutput:
    """Hand-written diffs prove the parser reads what this file writes. Git proves more."""

    def test_parses_a_diff_git_actually_produced(self, tmp_path: Path) -> None:
        """Builds a throwaway repo under tmp_path and checks a real ``git diff``."""
        repo = tmp_path / "repo"
        (repo / "scripts").mkdir(parents=True)
        run = lambda *a: subprocess.run(  # noqa: E731
            ["git", *a], cwd=repo, capture_output=True, text=True, check=True
        )
        run("init", "-q")
        run("config", "user.email", "t@example.com")
        run("config", "user.name", "t")
        target = repo / "scripts" / "guard.py"
        target.write_text("original = 1\n", encoding="utf-8")
        run("add", "-A")
        run("commit", "-qm", "base")
        target.write_text("original = 1\nCOMMAND_TEXT_RE = 2\n", encoding="utf-8")
        diff = run("diff").stdout
        assert diff.strip(), "git produced no diff — the fixture, not the parser, is broken"

        facts = vpnt.parse_diff(diff)
        assert "scripts/guard.py" in facts.files, facts.changed_lines
        events = write_events(tmp_path, make_record())
        result = vpnt.verify(events, diff)
        assert result["exit_code"] == vpnt.EXIT_FAILED
        assert "CONTRADICTED" in kinds(result)

    def test_a_new_file_in_a_real_diff_is_attributed(self, tmp_path: Path) -> None:
        """``--- /dev/null`` must not swallow the added file's lines."""
        repo = tmp_path / "repo2"
        repo.mkdir()
        run = lambda *a: subprocess.run(  # noqa: E731
            ["git", *a], cwd=repo, capture_output=True, text=True, check=True
        )
        run("init", "-q")
        run("config", "user.email", "t@example.com")
        run("config", "user.name", "t")
        (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
        run("add", "-A")
        run("commit", "-qm", "base")
        (repo / "new_module.py").write_text("\n".join(f"line{i}" for i in range(30)), "utf-8")
        run("add", "-A")
        diff = run("diff", "--cached").stdout
        facts = vpnt.parse_diff(diff)
        assert "new_module.py" in facts.changed_lines, facts.changed_lines
        assert facts.changed_lines["new_module.py"] >= 29


# ---------------------------------------------------------------------------
# 6. The instructions — pinned to the checker, not to their own wording
# ---------------------------------------------------------------------------


def field_labels(text: str) -> list[list[str]]:
    """Every ``## Path Not Taken`` template's field labels, in order, from a command file.

    Args:
        text: A command file's full text.

    Returns:
        One list of lowercase field names per template found.
    """
    out: list[list[str]] = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        # The template appears both as plain markdown (/plan's spec block) and as the first
        # line of a shell string argument (/build_module's write_event call), so a leading
        # quote is stripped before comparing.
        if line.strip().lstrip('"').strip() != vpnt.RECORD_HEADING:
            continue
        labels: list[str] = []
        for candidate in lines[i + 1 :]:
            match = re.match(r"\s*- \*\*(.+?)\*\*:", candidate)
            if not match:
                break
            labels.append(match.group(1).strip().lower())
        out.append(labels)
    return out


#: How many names a slash/pipe-separated run must reach before it is read as a COPY of the
#: per-record status vocabulary rather than a deliberate mention of a subset. Two is a real
#: pattern in `/review` (a shell comment naming the blocking pair, `CONTRADICTED / PHANTOM`),
#: so the floor sits above it. The cost of that choice, stated rather than hidden: a copy that
#: enumerates only two of the five is not caught by :func:`status_enumerations`.
ENUMERATION_FLOOR = 3


def status_enumerations(text: str) -> list[tuple[int, set[str]]]:
    """Every place ``text`` enumerates the checker's per-record statuses as a list.

    A run is consecutive :data:`verify_paths_not_taken.RECORD_STATUSES` names separated by
    nothing but whitespace, backticks, commas and at least one ``/`` or ``|``. Longest name
    first, so ``CONTRADICTED-IN-PROSE`` is never scored as ``CONTRADICTED``.

    Args:
        text: A command file's full text.

    Returns:
        ``(1-based line number, set of status names)`` for each run of at least
        :data:`ENUMERATION_FLOOR` names.
    """
    pattern = re.compile(
        "|".join(re.escape(name) for name in sorted(vpnt.RECORD_STATUSES, key=len, reverse=True))
    )
    hits = [(m.start(), m.end(), m.group(0)) for m in pattern.finditer(text)]
    runs: list[list[tuple[int, int, str]]] = []
    for hit in hits:
        gap = text[runs[-1][-1][1] : hit[0]] if runs else ""
        if runs and re.fullmatch(r"[\s`/|,]*", gap) and re.search(r"[/|]", gap):
            runs[-1].append(hit)
        else:
            runs.append([hit])
    return [
        (text[: run[0][0]].count("\n") + 1, {h[2] for h in run})
        for run in runs
        if len(run) >= ENUMERATION_FLOOR
    ]


class TestCommandsAndCheckerAgree:
    """Claims restated in two places must fail when the two disagree."""

    @pytest.mark.parametrize("path", [BUILD_MODULE, PLAN])
    def test_the_template_fields_match_the_checker_exactly(self, path: Path) -> None:
        """The six fields and their order are stated in the prose AND enforced in the script."""
        templates = field_labels(path.read_text(encoding="utf-8"))
        assert templates, f"{path.name} carries no '{vpnt.RECORD_HEADING}' template any more"
        for labels in templates:
            assert labels == list(vpnt.REQUIRED_FIELDS), (
                f"{path.name} teaches fields {labels} but "
                f"scripts/verify_paths_not_taken.py requires {list(vpnt.REQUIRED_FIELDS)}. "
                "A builder following the command would write a record the checker rejects."
            )

    @pytest.mark.parametrize("path", [BUILD_MODULE, PLAN, REVIEW])
    def test_the_record_tag_is_the_tag_the_checker_reads(self, path: Path) -> None:
        """Records are found by tag; a drifted tag makes every record invisible."""
        assert vpnt.RECORD_TAG in path.read_text(encoding="utf-8"), (
            f"{path.name} no longer names the tag {vpnt.RECORD_TAG!r} that "
            "scripts/verify_paths_not_taken.py reads records by"
        )

    @pytest.mark.parametrize("path", [BUILD_MODULE, PLAN])
    def test_the_minimum_falsifier_length_in_prose_matches_the_constant(self, path: Path) -> None:
        """A number quoted in an instruction is a claim about code and rots like one."""
        text = path.read_text(encoding="utf-8")
        quoted = re.findall(r"under (\d+)\s*\n?\s*characters", text)
        assert quoted, f"{path.name} no longer states the falsifier length floor"
        for value in quoted:
            assert int(value) == vpnt.MIN_FALSIFIER_LENGTH, (
                f"{path.name} says {value} characters, the checker enforces "
                f"{vpnt.MIN_FALSIFIER_LENGTH}"
            )

    def test_the_vague_examples_in_the_prose_are_really_rejected(self) -> None:
        """The command quotes examples of a bad falsifier. Each must actually be refused."""
        text = BUILD_MODULE.read_text(encoding="utf-8")
        # Fenced blocks are stripped first: an unpaired ``` shifts every subsequent
        # single-backtick pairing, which silently made this check see nothing.
        prose = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        quoted = re.findall(r"`([^`\n]+)`", prose)
        cited = [q for q in quoted if q.strip().lower() in vpnt.VAGUE_FALSIFIERS]
        assert cited, (
            "build_module.md quotes no example of a rejected falsifier; the instruction is "
            "abstract where it needs to be concrete"
        )
        for example in cited:
            record = vpnt.Record(
                fields={
                    "decision": "d",
                    "chosen": "c",
                    "rejected": "r",
                    "why rejected": "w",
                    "files": "src/a.py",
                    "falsifier": example,
                },
                source="prose example",
            )
            problems = vpnt._structural_problems(record)
            assert any(p.kind == "UNFALSIFIABLE" for p in problems), (
                f"build_module.md teaches {example!r} as a rejected falsifier but the checker "
                "accepts it"
            )

    @pytest.mark.parametrize("path", [REVIEW, BUILD_MODULE])
    def test_every_exit_code_is_documented_where_it_is_branched_on(self, path: Path) -> None:
        """A command that reads the exit code must document all four, with distinct meanings."""
        text = path.read_text(encoding="utf-8")
        for code, word in VERDICT_WORDS.items():
            assert re.search(rf"\*\*{code}\b", text), (
                f"{path.name} branches on scripts/verify_paths_not_taken.py but does not "
                f"document exit {code} ({word}). An undocumented code gets collapsed into "
                "its neighbour, which is how 'could not read' becomes 'nothing wrong'."
            )

    def test_the_exit_zero_verdict_is_not_the_word_verified(self) -> None:
        """The headline word must not claim more than the run did.

        This is the sharpest drift this suite guards, and it was the one thing
        ``TestCommandsAndCheckerAgree`` had no coverage of. The module docstring, the honest-limits
        tests, and ``/review`` all said exit 0 means "nothing refuted *in code*" — and the string
        the script PRINTED said ``VERIFIED``. Measured 2026-08-09, before the fix: a record written
        to be false on purpose (straw-man alternative, falsifier absent by construction) checked
        against the checker's own 1099-line diff printed
        ``PATHS_NOT_TAKEN: VERIFIED -- 1 record(s) checked``, exit 0. A tool whose prose and
        headline disagree is judged on the headline, and the headline is the token that propagates
        into ``verifier_exit_code`` and into what a developer is taught.
        """
        assert vpnt.VERDICT_WORDS[vpnt.EXIT_OK] != "VERIFIED", (
            "exit 0 prints VERIFIED again. The script cannot verify anything: it reports "
            "whether a string is absent. VERIFIED is a verdict only the Step 10 reader awards."
        )
        assert vpnt.VERDICT_WORDS[vpnt.EXIT_OK] == vpnt.STATUS_CLEAR, (
            "the exit-0 verdict and the per-record clear status have drifted into two words for "
            "one fact"
        )

    def test_the_printed_exit_zero_header_carries_the_word_and_its_caveat(
        self, tmp_path: Path
    ) -> None:
        """Rendered output, not just the constant — the constant could be bypassed in `_render`."""
        events = write_events(tmp_path, make_record())
        result = vpnt.verify(events, make_diff("scripts/guard.py", ["def check(): ..."]))
        assert result["exit_code"] == vpnt.EXIT_OK, result["problems"]
        rendered = vpnt._render(result)
        headline = rendered.splitlines()[0]
        # Scoped to the HEADLINE, not the whole render: the caveat legitimately contains the
        # string "not VERIFIED", and a blanket search would forbid the sentence that does the
        # work. What must never carry the word is the line a reader quotes as the verdict.
        assert vpnt.VERDICT_WORDS[vpnt.EXIT_OK] in headline
        assert "VERIFIED" not in headline, (
            f"the exit-0 headline still reads {headline!r} -- the word VERIFIED is what "
            "propagates into verifier_exit_code and into what a developer is taught"
        )
        assert result["caveat"], "exit 0 carries no caveat in the --json payload /review reads"
        assert "not VERIFIED" in str(result["caveat"])
        assert str(result["caveat"]) in rendered, (
            "the caveat reaches the JSON payload but not the text render, so a human run and the "
            "machine run disagree about what exit 0 means"
        )

    def test_review_promises_exactly_the_per_record_statuses_the_checker_emits(self) -> None:
        """Condition 2's drift: the command promised a per-record tag the result had no field for.

        ``/review``'s hand-off block requires each claim tagged with one of five words. Before this
        guard existed the result carried only a flat ``problems`` list — no per-record status at
        all — so the promise was made by the command and kept by nobody, and this class, whose
        entire job is command/checker drift, had **zero** assertions about that vocabulary.
        """
        text = REVIEW.read_text(encoding="utf-8")
        promised = re.search(
            r"per-record status:\s*([A-Z\- /\n]+?)\.\]",
            text,
        )
        assert promised, "/review's hand-off block no longer lists a per-record status vocabulary"
        words = {w.strip() for w in re.split(r"[/\n]", promised.group(1)) if w.strip()}
        assert words == set(vpnt.RECORD_STATUSES), (
            f"/review promises the briefing agent {sorted(words)} but the checker emits "
            f"{sorted(vpnt.RECORD_STATUSES)}. A status the command names and the script never "
            "sets cannot be copied across, and one the script sets and the command never names "
            "has no instruction attached to it."
        )

    def test_every_copy_of_the_status_vocabulary_in_review_is_the_whole_set(self) -> None:
        """The sibling above pins ONE copy. `/review` carries more than one, and the one the
        consumer actually reads was the unpinned one.

        Census taken 2026-08-09. ``RECORD_STATUSES`` is the authority; the vocabulary is then
        restated in three places, and until this test existed only two were guarded:

        * `/review` Step 7's hand-off block — pinned by the sibling above, whose regex
          (``per-record status: ... .]``) matches that block and nothing else in the file
          (measured: exactly one match).
        * `.claude/commands/walkthrough.md` — pinned by ``tests/test_education_gate.py``.
        * `/review` Step 10's contract — pinned by **nothing**. And Step 10 is the copy that
          matters most: `walkthrough.md` sends the briefing agent to Step 10 as authoritative
          and explicitly forbids restating the list, so the words the consumer reads are read
          from the copy no test was holding still.

        Structural, not cosmetic — a status renamed in the script would have left Step 10 naming
        a word nothing emits, in the one place a reader is told to trust over their own file.
        """
        text = REVIEW.read_text(encoding="utf-8")
        found = status_enumerations(text)
        assert len(found) >= 2, (
            f"/review carries {len(found)} enumeration(s) of the per-record status vocabulary; "
            "the Step 7 hand-off block and the Step 10 contract each carry one. If a copy moved "
            "or was folded away, re-point this census rather than lowering it — the failure mode "
            "it guards is a copy nobody is watching."
        )
        for line, words in found:
            assert words == set(vpnt.RECORD_STATUSES), (
                f"/review line {line} enumerates the per-record statuses as {sorted(words)}, but "
                f"the checker emits {sorted(vpnt.RECORD_STATUSES)}. Missing: "
                f"{sorted(set(vpnt.RECORD_STATUSES) - words)}; invented: "
                f"{sorted(words - set(vpnt.RECORD_STATUSES))}."
            )
        step_10 = text.index("## Step 10: Education Gate")
        step_10_line = text[:step_10].count("\n") + 1
        assert any(line > step_10_line for line, _ in found), (
            "the Step 10 contract no longer enumerates the status vocabulary. walkthrough.md "
            "sends the briefing agent here as authoritative and forbids restating the list, so a "
            "Step 10 that names no vocabulary leaves the consumer with nowhere to read it from."
        )
        assert any(line < step_10_line for line, _ in found), (
            "the Step 7 hand-off block no longer enumerates the status vocabulary the briefing "
            "agent is told to copy across from the run"
        )

    def test_every_problem_kind_reaches_a_per_record_status(self, tmp_path: Path) -> None:
        """Provoke each kind and assert the RECORD carries it, not just the problem list."""
        cases = {
            "CONTRADICTED": (
                make_record(),
                make_diff("scripts/guard.py", ["COMMAND_TEXT_RE = 1"]),
            ),
            "PHANTOM": (
                make_record(Files="src/nowhere.py"),
                make_diff("scripts/guard.py", ["x = 1"]),
            ),
            "UNFALSIFIABLE": (
                make_record(Falsifier="n/a"),
                make_diff("scripts/guard.py", ["x = 1"]),
            ),
            "CONTRADICTED-IN-PROSE": (
                make_record(Falsifier="lru_cache"),
                make_diff("scripts/guard.py", ["# rejected lru_cache: unbounded keys"]),
            ),
            vpnt.STATUS_CLEAR: (make_record(), make_diff("scripts/guard.py", ["ok = 1"])),
        }
        for index, (expected, (record, diff)) in enumerate(cases.items()):
            case_dir = tmp_path / f"case{index}"
            case_dir.mkdir()
            result = vpnt.verify(write_events(case_dir, record), diff, min_changed_lines=999)
            statuses = result["record_status"]
            assert isinstance(statuses, list) and len(statuses) == 1, statuses
            assert statuses[0]["status"] == expected, (
                f"a record that draws {expected} is reported as {statuses[0]['status']!r} "
                "per-record; the briefing agent would tag the wrong claim"
            )
            assert statuses[0]["status"] in vpnt.RECORD_STATUSES

    def test_a_blocking_kind_outranks_an_advisory_one_on_the_same_record(
        self, tmp_path: Path
    ) -> None:
        """One record, two files: reporting the advisory would hide the refutation."""
        record = make_record(Files="scripts/guard.py, docs/note.md", Falsifier="lru_cache")
        diff = make_diff("scripts/guard.py", ["cache = lru_cache(None)"]) + make_diff(
            "docs/note.md", ["we rejected lru_cache here"]
        )
        result = vpnt.verify(write_events(tmp_path, record), diff, min_changed_lines=999)
        emitted = kinds(result)
        assert "CONTRADICTED" in emitted and "CONTRADICTED-IN-PROSE" in emitted, emitted
        statuses = result["record_status"]
        assert isinstance(statuses, list)
        assert statuses[0]["status"] == "CONTRADICTED", (
            "the per-record status reported the advisory kind while a blocking one was also "
            "raised against the same record, which launders a refutation into a footnote"
        )

    def test_review_documents_every_problem_kind_the_checker_can_emit(
        self, tmp_path: Path
    ) -> None:
        """Kinds are MEASURED by provoking each one, not copied from a list in this file."""
        emitted: set[str] = set()
        cases = [
            (make_record(), make_diff("scripts/guard.py", ["COMMAND_TEXT_RE = 1"]), 20),
            (make_record(Files="src/nowhere.py"), make_diff("scripts/guard.py", ["x = 1"]), 20),
            (make_record(Falsifier="n/a"), make_diff("scripts/guard.py", ["x = 1"]), 20),
            (
                make_record(),
                make_diff("scripts/guard.py", ["ok = 1"])
                + make_diff("src/silent.py", [f"l{i}" for i in range(30)]),
                20,
            ),
        ]
        cases.append(
            (
                make_record(Falsifier="lru_cache"),
                make_diff(
                    "scripts/guard.py", ["# rejected lru_cache because the keys are unbounded"]
                ),
                999,
            )
        )
        for index, (record, diff, threshold) in enumerate(cases):
            case_dir = tmp_path / f"case{index}"
            case_dir.mkdir()
            events = write_events(case_dir, record)
            emitted.update(kinds(vpnt.verify(events, diff, min_changed_lines=threshold)))
        assert emitted == {
            "CONTRADICTED",
            "CONTRADICTED-IN-PROSE",
            "PHANTOM",
            "UNFALSIFIABLE",
            "UNRECORDED",
        }, emitted

        text = REVIEW.read_text(encoding="utf-8")
        missing = sorted(kind for kind in emitted if kind not in text)
        assert not missing, (
            f"/review does not name the verdicts {missing} that the checker actually emits. "
            "A reviewer who meets an undocumented kind has no instruction for what to do."
        )


class TestTheInstructionLandsAtTheMomentOfDecision:
    """The timing IS the mechanism: a record written afterwards is a reconstruction."""

    def test_the_record_step_sits_inside_the_per_task_loop(self) -> None:
        """Structural, so rewording the step is fine and moving it out of the loop is not."""
        text = BUILD_MODULE.read_text(encoding="utf-8")
        start = text.index("### Step 3a: Generate Code")
        end = text.index("### Step 3b: Checkpoint Evaluation")
        assert vpnt.RECORD_HEADING in text[start:end], (
            "the path-not-taken template no longer sits between code generation and the "
            "checkpoint. Outside the per-task loop it becomes a closing summary step, which is "
            "a reconstruction written through the lens of what shipped -- the exact artifact "
            "this mechanism exists to avoid."
        )

    def test_the_loop_preamble_names_the_record_step(self) -> None:
        """A step the loop header does not name is a step that gets skipped."""
        text = BUILD_MODULE.read_text(encoding="utf-8")
        preamble = text[text.index("## Step 3: Execute Tasks") : text.index("### Step 3a:")]
        assert "3a.5" in preamble, (
            "Step 3's loop header lists the steps to run per task and no longer includes the "
            "record step"
        )

    def test_the_timing_is_stated_as_a_reason_not_only_as_an_order(self) -> None:
        """An instruction whose 'why' is missing is the first one dropped under pressure."""
        text = BUILD_MODULE.read_text(encoding="utf-8")
        assert "reconstruction" in text.lower(), (
            "build_module.md no longer explains WHY the record must be written while deciding"
        )

    def test_plan_records_at_spec_time_and_not_as_a_closing_pass(self) -> None:
        """/plan's rejected approaches are the highest-value ones; they belong in the spec."""
        text = PLAN.read_text(encoding="utf-8")
        spec_start = text.index("## Step 2: Produce Structured Spec")
        spec_end = text.index("## Step 3: Create Discussion")
        section = text[spec_start:spec_end]
        assert "## Paths Not Taken" in section, "the spec template no longer carries the section"
        assert vpnt.RECORD_HEADING in section, "the spec template no longer carries a record block"

    def test_plan_pushes_its_records_into_layer_one(self) -> None:
        """A spec section can be edited without trace; Layer 1 is append-only."""
        text = PLAN.read_text(encoding="utf-8")
        assert "write_event.py" in text[text.index("## Paths Not Taken") :], (
            "/plan records the paths not taken only in the spec document. Nothing then makes "
            "them append-only or queryable, and the verifier reads Layer 1."
        )


class TestFailedVerificationHasAConsequence:
    """A check with no consequence is inert prose that reads as a mechanism."""

    def test_review_runs_the_checker_rather_than_describing_it(self) -> None:
        """The command must contain the invocation, not a suggestion to verify somehow."""
        text = REVIEW.read_text(encoding="utf-8")
        assert "scripts/verify_paths_not_taken.py" in text
        assert re.search(r"git diff[^\n]*\|[^\n]*verify_paths_not_taken\.py", text), (
            "/review no longer pipes a real diff into the checker; a verification step that "
            "does not run is the failure mode this slice exists to prevent"
        )

    def test_a_failed_verification_floors_the_verdict(self) -> None:
        """Exit 1 must cost something. 'approve' must be unavailable."""
        text = REVIEW.read_text(encoding="utf-8")
        block = text[text.index("## Step 6.4") : text.index("## Step 6.5")]
        assert "approve-with-changes" in block and "may not return `approve`" in block, (
            "the exit-1 branch of /review no longer states a consequence for the review "
            "verdict. Without one the check is decoration."
        )

    def test_a_failed_verification_is_captured_as_a_finding(self) -> None:
        """The consequence must survive the session, not live in a transcript."""
        block = REVIEW.read_text(encoding="utf-8")
        block = block[block.index("## Step 6.4") : block.index("## Step 6.5")]
        assert "write_event.py" in block, "the verification result is never captured"
        assert "Severity:" in block, (
            "a refuted record is not written with an explicit severity marker, so "
            "scripts/extract_findings.py cannot turn it into a queryable finding row"
        )

    def test_the_result_is_captured_even_when_it_passes(self) -> None:
        """A green result must be evidence, not silence — otherwise absence proves nothing."""
        text = REVIEW.read_text(encoding="utf-8")
        block = text[text.index("## Step 6.4") : text.index("## Step 6.5")]
        assert re.search(r"even on exit\s*0", block, flags=re.I), (
            "/review captures only failures, so a discussion with no verification event is "
            "ambiguous between 'verified clean' and 'never checked'"
        )

    def test_the_enforcement_limit_is_stated_rather_than_implied(self) -> None:
        """No hook reads this exit code. Saying so is the difference from overclaiming."""
        text = REVIEW.read_text(encoding="utf-8")
        block = text[text.index("## Step 6.4") : text.index("## Step 6.5")]
        assert "pre-commit" in block and "quality gate" in block, (
            "/review no longer states that nothing mechanical enforces the verdict floor. An "
            "unstated limit reads as a guarantee the code has never made."
        )


class TestTheBriefingAgentContract:
    """The hand-off is defined by content, not by the education gate's current shape."""

    def test_the_handoff_block_is_defined_in_the_report(self) -> None:
        """The briefing agent's input must exist somewhere it can actually be read."""
        text = REVIEW.read_text(encoding="utf-8")
        assert "## Paths Not Taken — Verification Handoff" in text
        for key in (
            "discussion_ids",
            "diff_command",
            "verifier_exit_code",
            "records_checked",
            "records_refuted",
            "files_unspoken_for",
        ):
            assert key in text, f"the hand-off block no longer carries {key!r}"

    def test_the_handoff_enumerates_every_exit_code_the_checker_can_return(self) -> None:
        """`verifier_exit_code` listed ``[0 | 1 | 2 | NOT RUN]`` — and the checker returns 3 too.

        The omission was not cosmetic. `walkthrough.md` branches on ``verifier_exit_code: 3``
        specifically (instrument failure: the checker could not read its own evidence, so nothing
        was verified) and treats it differently from an absent handoff. A field whose stated
        domain excludes 3 tells the report writer to round it to a neighbour — ``NOT RUN``, which
        means nobody asked, or ``0``, which means nothing was refuted. Both launder "could not
        read the evidence" into "nothing wrong", the one confusion this whole step exists to stop.

        The sibling ``test_every_exit_code_is_documented_where_it_is_branched_on`` does not cover
        this: it matches the bold ``**N —`` headers in Step 6.4, not the field's own enumeration.
        """
        text = REVIEW.read_text(encoding="utf-8")
        field = re.search(r"\*\*verifier_exit_code\*\*:\s*\[([^\]]*)\]", text, flags=re.S)
        assert field, "the hand-off block no longer states a domain for verifier_exit_code"
        # The DOMAIN only — the alternatives before the em-dash that introduces the rationale.
        # Scoping matters: the rationale prose legitimately names both `3` and `NOT RUN` while
        # explaining why they are different facts, so searching the whole bracket would let the
        # enumeration itself lose either one and still read green off its own explanation.
        domain = field.group(1).split("—")[0]
        listed = {int(n) for n in re.findall(r"\b(\d)\b", domain)}
        assert listed == set(VERDICT_WORDS), (
            f"verifier_exit_code offers {sorted(listed)} but the checker can return "
            f"{sorted(VERDICT_WORDS)}. Missing: {sorted(set(VERDICT_WORDS) - listed)} — an "
            "unlisted code gets rounded into a neighbour by whoever fills the block in."
        )
        assert "NOT RUN" in domain, (
            "verifier_exit_code no longer offers NOT RUN, so a review that never ran the checker "
            "has to invent a number"
        )

    def test_the_contract_promises_the_scope_field_its_consumer_depends_on(self) -> None:
        """ "Nothing else may be depended on" has to cover what the consumer actually reads.

        Step 10 said the briefing agent receives *exactly* the handoff block and that nothing else
        is promised. But binding a handoff to a change needs the report's ``reviewed_files``
        frontmatter — the block itself carries no scope field, so the newest report carrying the
        heading could belong to a later, unrelated change and read as this one's. `walkthrough.md`
        already reads that frontmatter; the contract simply did not promise it. A contract that
        under-promises what its consumer depends on breaks silently the first time the unnamed
        half moves, and the "nothing else" clause makes the consumer's real dependency look like
        a violation.
        """
        text = REVIEW.read_text(encoding="utf-8")
        gate = text[text.index("## Step 10: Education Gate") :]
        receives = gate[gate.index("**Receives**") : gate.index("**Must do")]
        assert "reviewed_files" in receives, (
            "Step 10's Receives clause does not name `reviewed_files`, so the briefing agent has "
            "no promised way to tell that the newest report carrying the handoff heading is the "
            "handoff for THIS change"
        )
        assert re.search(r"nothing else (is promised|may be depended)", receives, flags=re.I), (
            "Step 10 no longer closes the interface. An open-ended Receives clause lets the "
            "briefing agent depend on report internals a rebuilt /review may move."
        )

    def test_step_10_consumes_exactly_that_block(self) -> None:
        """The contract is the block; naming another file would couple to a sibling's internals."""
        text = REVIEW.read_text(encoding="utf-8")
        gate = text[text.index("## Step 10: Education Gate") :]
        assert "Paths Not Taken — Verification Handoff" in gate, (
            "Step 10 no longer names the hand-off block it consumes"
        )
        for foreign in ("educator.md", "quiz.md", "walkthrough.md"):
            assert foreign not in gate, (
                f"Step 10 depends on the internal shape of {foreign}, which a sibling slice is "
                "rebuilding. The contract must be the payload, not the other side's file."
            )

    def test_the_recommendation_carries_the_report_path(self) -> None:
        """An obligation nobody is handed is not an obligation.

        The contract is defined in terms of a block inside ``docs/reviews/REV-*.md``, and — as of
        this slice — nothing on the education-gate side references that path, that heading, or
        the tag (the grep and its zero result live in Step 6.4). So the ONLY thing carrying the
        obligation across is this command telling the briefing agent where the block is. Drop the
        path from the recommendation and the whole Step 10 contract is inert prose.
        """
        text = REVIEW.read_text(encoding="utf-8")
        gate = text[text.index("## Step 10: Education Gate") :]
        recommendation = gate[: gate.index("### The briefing agent")]
        assert "docs/reviews/" in recommendation, (
            "/review recommends the education gate without passing the report path, so the "
            "briefing agent never learns the hand-off block exists and cannot honour a contract "
            "it has not been shown"
        )
        assert "Paths Not Taken — Verification Handoff" in recommendation, (
            "the recommendation names a report but not the section inside it that carries the "
            "obligation"
        )

    def test_the_seam_claim_ships_with_the_command_that_re_measures_it(self) -> None:
        """A dated claim about another file's contents must carry its own re-measurement.

        This guard used to REQUIRE the opposite claim. Until 2026-08-09 it asserted that Step 6.4
        still said the education gate "does not yet read" the hand-off — and by then a sibling
        slice had wired it. Re-running Step 6.4's own published grep verbatim returned **11**
        hits (8 in `.claude/commands/walkthrough.md`, 3 in `.claude/commands/quiz.md`; still 0 in
        `.claude/agents/educator.md` and `scripts/education/`), so the command was shipping a
        false measurement as live model-facing instruction, and this test was holding it there.

        So the guard no longer pins a world-state at all — that is the thing that rotted. It pins
        the two properties that stay true whichever way the seam goes: the reproducing command is
        still published, and the retired zero-hit reading is not asserted again. The count itself
        is deliberately NOT asserted here: this suite must not become the second place a stale
        number has to be corrected.
        """
        text = REVIEW.read_text(encoding="utf-8")
        block = text[text.index("## Step 6.4") : text.index("## Step 6.5")]
        grep_line = next(
            (ln for ln in block.splitlines() if ln.strip().startswith("grep -rn")), ""
        )
        assert grep_line, (
            "the disclosure states a claim about the education gate without the command that "
            "reproduces it, so the next reader cannot re-measure whether it is still true"
        )
        # ...and the command must still search for the seam. A grep whose terms have drifted off
        # the handoff is a re-measurement of nothing that reports clean.
        for term in ("docs/reviews", "Paths Not Taken"):
            assert term in grep_line, (
                f"Step 6.4's published grep no longer searches for {term!r}, so it can no longer "
                "measure whether the education gate reads the handoff"
            )
        # The retired reading, in the words the file used to carry it. Allowed ONLY where a
        # repudiation marker PRECEDES it closely — i.e. the phrase is being quoted as dead, not
        # asserted. A trailing marker would not do: restoring the false sentence directly above
        # the "an earlier version said..." paragraph would then pass while re-asserting it.
        retired = (r"does not yet read", r"not wired", r"zero\**\s*hits")
        for phrase in retired:
            for match in re.finditer(phrase, block, flags=re.I):
                before = block[max(0, match.start() - 200) : match.start()]
                assert re.search(
                    r"(earlier version|do not restore|used to|no longer)", before, re.I
                ), (
                    f"/review asserts the retired {block[match.start() : match.end()]!r} reading "
                    "of the education-gate seam again. Slice A wired it and the grep this block "
                    "publishes returns hits; re-measure before restating either half."
                )

    def test_the_briefing_agent_must_rerun_the_checker(self) -> None:
        """Trusting the report's copied exit code is trusting the party being checked.

        Asserted as a RELATION (the checker is named, and the copied exit code is refused within
        the same passage) rather than as one literal sentence, so a benign rewording survives and
        a deleted obligation does not.
        """
        text = REVIEW.read_text(encoding="utf-8")
        gate = text[text.index("## Step 10: Education Gate") :]
        assert "verify_paths_not_taken.py" in gate
        assert re.search(r"(do not|don't|never)\s+trust[^.]{0,60}exit code", gate, flags=re.I), (
            "Step 10 no longer refuses the report's copied exit code, so the briefing agent may "
            "verify by reading the transcript written by the party being checked"
        )

    def test_an_instrument_failure_is_stated_loudly_and_does_not_block_the_gate(self) -> None:
        """A broken checker may not withhold a HUMAN's briefing. Loud, not blocking.

        Obligation 1 read *"Exit 3 means the gate cannot proceed — say so and stop"* until
        2026-08-09. `walkthrough.md` Step 2a imports these obligations verbatim ("work the
        numbered list as written there", and it forbids restating them), so that sentence made an
        INSTRUMENT FAILURE hard-gate a human's education gate — re-creating by another route the
        exact Principle #5 violation the Steward struck from this same file, and contradicting the
        walkthrough's own "never blocks, delays, or withholds" posture two screens away.

        Principle #5 makes briefing offered, not withheld, and names exactly two non-declinable
        classes: framework governance/safety changes, and distribution to derived projects. A
        checker that fell over is neither. The honesty is the part worth keeping — exit 3 means
        nothing was verified, and saying "clean" would be the worse failure — so this guard
        requires BOTH halves: the failure is stated, and it does not stop the gate.
        """
        text = REVIEW.read_text(encoding="utf-8")
        gate = text[text.index("## Step 10: Education Gate") :]
        match = re.search(r"[Ee]xit 3", gate)
        assert match, (
            "Step 10 no longer says what the briefing agent does on an instrument failure"
        )
        passage = gate[match.start() : match.start() + 900]
        assert re.search(r"(does NOT stop|not stop|never blocks?|does not block)", passage), (
            "Step 10 no longer states that exit 3 leaves the gate completable. An instrument "
            "failure that halts the briefing is a third non-declinable class; Principle #5 "
            "defines exactly two, and a broken checker is not one of them."
        )
        assert re.search(r"(unchecked|nothing was verified|could not read)", passage), (
            "Step 10 no longer says that exit 3 means nothing was verified. Dropping the block "
            "only helps if the honesty survives — a silent instrument failure reads as clean."
        )
        # The struck instruction, and its near-synonyms, may not come back.
        for banned in (r"cannot proceed", r"say so and stop", r"and stop\b"):
            assert not re.search(banned, passage, flags=re.I), (
                f"Step 10's exit-3 passage tells the briefing agent to {banned!r}. That is a hard "
                "gate on a human's briefing, off an instrument failure, on the one surface where "
                "the developer's steer was verbatim \"I don't want to make it onerous and "
                'hard-gating".'
            )

    def test_a_refuted_claim_is_never_taught_as_fact(self) -> None:
        """The consequence at the gate. Without it the gate launders the fiction.

        A relation within a window rather than a fixed sentence: REFUTED must be tied to
        not-teaching.
        """
        text = REVIEW.read_text(encoding="utf-8")
        gate = text[text.index("## Step 10: Education Gate") :]
        assert re.search(r"REFUTED[\s\S]{0,160}?(never|not)\b[^.]{0,60}taught", gate), (
            "Step 10 no longer forbids teaching a REFUTED claim as fact, which is the whole "
            "consequence at the gate"
        )

    def test_a_refuted_claim_is_surfaced_rather_than_used_to_block_the_gate(self) -> None:
        """Principle #5's two non-declinable classes are the whole list; this is not a third.

        The sibling above ASSERTED THE OPPOSITE until 2026-08-09: it required Step 10 to say the
        education gate "cannot be recorded complete" while a REFUTED claim stands. That is a hard
        gate on a **human**, invented by the builder in the same round, on the one surface where
        the developer's steer was verbatim *"I don't want to make it onerous and hard-gating"* —
        and Principle #5 names exactly two classes where briefing is non-declinable (framework
        governance/safety changes, and distribution to derived projects). A refuted path-not-taken
        record is neither, so the guard was enforcing a rule the constitution does not contain.

        The BUILD-side friction is deliberately not covered here and must stay: `/build_module`
        behavioural rule 9 and Step 3a.5 fall on the agent, not on the developer.
        """
        text = REVIEW.read_text(encoding="utf-8")
        gate = text[text.index("## Step 10: Education Gate") :]
        assert re.search(r"REFUTED[\s\S]{0,200}?(surfaced|stated plainly)", gate), (
            "Step 10 no longer requires a REFUTED claim to be surfaced to the developer. Removing "
            "the block only helps if the finding is impossible to miss."
        )
        assert re.search(r"REFUTED[\s\S]{0,300}?(does NOT block|not block)", gate), (
            "Step 10 no longer states that a REFUTED claim leaves the gate completable"
        )
        # The old sentence may survive only as a QUOTE inside the passage that repudiates it.
        for match in re.finditer(r"recorded complete", gate):
            window = gate[max(0, match.start() - 600) : match.end() + 200]
            assert "Principle #5" in window, (
                "Step 10 makes the education gate non-completable on a REFUTED claim again. That "
                "is a third non-declinable briefing class; Principle #5 defines exactly two, and "
                "neither is this. Surface the finding, capture it, and let the human close."
            )

    def test_the_gate_covers_the_case_the_script_only_proxies(self) -> None:
        """Case 3 needs a reader: the script counts files, a reader can see choices."""
        text = REVIEW.read_text(encoding="utf-8")
        gate = text[text.index("## Step 10: Education Gate") :]
        assert "files_unspoken_for" in gate and "decision" in gate


class TestTheCheckersHonestLimits:
    """Executable statements of what this design does NOT catch.

    These tests pass today by asserting a *gap*. That is deliberate. If someone later claims the
    mechanism covers all three cases, one of these is the test they must delete to say so — which
    makes the overclaim visible in a diff instead of in a paragraph.
    """

    def test_a_semantically_false_record_with_a_clean_falsifier_passes(
        self, tmp_path: Path
    ) -> None:
        """Case 1 is only half-mechanical: the string search cannot read meaning."""
        record = make_record(
            Rejected="an in-process cache",
            Chosen="no caching at all",
            Falsifier="functools.lru_cache",
        )
        events = write_events(tmp_path, record)
        # The diff DOES add an in-process cache -- as a plain dict, so the falsifier is absent.
        diff = make_diff("scripts/guard.py", ["_seen = {}", "def check(k): return _seen.get(k)"])
        result = vpnt.verify(events, diff)
        assert result["exit_code"] == vpnt.EXIT_OK, (
            "if this now fails, the checker gained semantic reach and this honest-limit test "
            "should be rewritten -- do not simply delete it"
        )

    def test_a_decision_inside_a_small_hunk_is_never_flagged(self, tmp_path: Path) -> None:
        """Case 3 is a churn proxy. A three-line decision is invisible to it."""
        events = write_events(tmp_path, make_record())
        diff = make_diff("scripts/guard.py", ["ok = 1"]) + make_diff(
            "src/quiet.py", ["MODE = 'strict'"]
        )
        result = vpnt.verify(events, diff, min_changed_lines=vpnt.DEFAULT_MIN_CHANGED_LINES)
        assert "UNRECORDED" not in kinds(result)

    def test_a_precise_but_wrong_falsifier_passes(self, tmp_path: Path) -> None:
        """Structural checks cannot tell a right token from a plausible-looking wrong one."""
        events = write_events(tmp_path, make_record(Falsifier="Comand_Text_RE"))
        diff = make_diff("scripts/guard.py", ["COMMAND_TEXT_RE = 1"])
        result = vpnt.verify(events, diff)
        assert result["exit_code"] == vpnt.EXIT_OK

    def test_the_limits_are_written_down_where_a_reader_will_meet_them(self) -> None:
        """The gaps above must be stated in the command a reviewer actually reads."""
        text = REVIEW.read_text(encoding="utf-8")
        block = text[text.index("## Step 6.4") : text.index("## Step 6.5")]
        assert "proxy" in block, (
            "/review presents the coverage check without saying it counts files rather than "
            "decisions, which overstates what exit 2 means"
        )

    def test_an_approach_that_ships_as_prose_is_not_mechanically_caught(
        self, tmp_path: Path
    ) -> None:
        """The cost of not refuting a comment: prose that DOES adopt the approach passes.

        Stated as a test rather than as a sentence because it is a real gap opened on purpose.
        A command file that adopts the rejected wording is a genuine contradiction the string
        search now declines to call one -- the advisory is raised and the run stays green, and
        the briefing agent owns the judgement (``/review`` Step 10, obligation 2).
        """
        events = write_events(tmp_path, make_record(Files=".claude/commands/plan.md"))
        diff = make_diff(".claude/commands/plan.md", ["Use COMMAND_TEXT_RE to guard the block."])
        result = vpnt.verify(events, diff, min_changed_lines=999)
        assert result["exit_code"] == vpnt.EXIT_OK
        assert kinds(result) == ["CONTRADICTED-IN-PROSE"], (
            "the prose match must still be REPORTED. Silently dropping it would trade a false "
            "positive for an invisible false negative, which is worse than either"
        )


class TestATruthfulRecordIsNotMechanicallyRefuted:
    """The false-POSITIVE arms: shapes of honest work a naive checker blocks.

    Every test here fails on a checker that is merely strict. They exist because a blocking
    verdict against a true record is this instrument's worst outcome -- it is answered by
    ``/build_module``'s "fix the record", i.e. it instructs a builder to falsify a correct record
    to get green, which trains people to stop recording at all.
    """

    @pytest.mark.parametrize(
        "raw, expected",
        [
            (".claude/commands/plan.md", ".claude/commands/plan.md"),
            (".github/workflows/ci.yml", ".github/workflows/ci.yml"),
            (".env.example", ".env.example"),
            ("./src/a.py", "src/a.py"),
            ("  `scripts/x.py`  ", "scripts/x.py"),
            ("scripts" + chr(92) + "x.py", "scripts/x.py"),
        ],
    )
    def test_paths_normalise_without_eating_the_leading_dot(self, raw: str, expected: str) -> None:
        """``lstrip('./')`` takes a CHARACTER SET: it turned ``.claude/x`` into ``claude/x``.

        Measured on the pre-fix code: ``'.claude/commands/plan.md'.lstrip('./')`` ->
        ``'claude/commands/plan.md'``, which can never equal any path a diff reports.
        """
        record = vpnt.Record(fields={"files": raw}, source="t")
        assert record.files == [expected]

    @pytest.mark.parametrize(
        "path", [".claude/commands/plan.md", ".github/workflows/ci.yml", ".env.example"]
    )
    def test_a_record_about_a_dotfile_path_is_not_phantom(self, tmp_path: Path, path: str) -> None:
        """End to end: the governance tree is where these records matter most."""
        events = write_events(tmp_path, make_record(Files=path))
        result = vpnt.verify(events, make_diff(path, ["ok = 1"]), min_changed_lines=999)
        assert result["exit_code"] == vpnt.EXIT_OK, result["problems"]

    def test_a_dotfile_path_can_be_spoken_for_by_the_coverage_proxy(self, tmp_path: Path) -> None:
        """The same bug silently disabled coverage: a mangled path is never in ``spoken_for``."""
        events = write_events(tmp_path, make_record(Files=".claude/commands/plan.md"))
        diff = make_diff(".claude/commands/plan.md", [f"line{i}" for i in range(30)])
        result = vpnt.verify(events, diff, min_changed_lines=20)
        assert "UNRECORDED" not in kinds(result), (
            "a high-churn .claude/ file the record explicitly names was reported unspoken-for"
        )

    def test_a_comment_explaining_the_rejection_does_not_refute_the_record(
        self, tmp_path: Path
    ) -> None:
        """Documenting why you rejected an approach must not refute the record of rejecting it."""
        events = write_events(tmp_path, make_record(Falsifier="lru_cache"))
        diff = make_diff("scripts/guard.py", ["# we deliberately do NOT use lru_cache here"])
        result = vpnt.verify(events, diff, min_changed_lines=999)
        assert result["exit_code"] == vpnt.EXIT_OK, result["problems"]
        assert kinds(result) == ["CONTRADICTED-IN-PROSE"]

    @pytest.mark.parametrize("prefix", vpnt.COMMENT_PREFIXES)
    def test_every_comment_prefix_is_really_treated_as_prose(self, prefix: str) -> None:
        """The constant is the contract; each entry must actually suppress the refutation.

        Parametrised from the constant itself rather than from a hand-copied list, which had
        drifted: the copy omitted ``/*``, ``\"\"\"`` and ``'''`` entirely, so three entries were
        never exercised.
        """
        assert vpnt.is_prose_line("src/a.py", f"  {prefix} mentions lru_cache")

    @pytest.mark.parametrize(
        "path, line",
        [
            ("scripts/deploy.sh", "--patch-guard \\"),
            ("src/a.py", "*args,"),
            ("src/a.py", "**kwargs,"),
            ("Makefile", "--strict-mode"),
        ],
    )
    def test_a_code_line_starting_with_a_comment_marker_is_still_code(
        self, path: str, line: str
    ) -> None:
        """The carve-out must not blind the checker to lines that merely start like comments.

        Measured on the pre-fix constants: ``is_prose_line('scripts/x.sh', '--patch-guard \\\\')``
        and ``is_prose_line('src/a.py', '*args,')`` both returned True, because
        ``COMMENT_PREFIXES`` held bare ``--`` and ``*``. A shell continuation ``--patch-guard`` is
        shape AND is one of ``/build_module``'s four taught-good falsifiers, so the command taught
        an example its own checker downgraded to advisory. Requiring the trailing space fixes it
        without losing the real comment shapes (covered by the parametrised test above).
        """
        assert not vpnt.is_prose_line(path, line)

    def test_every_falsifier_the_command_teaches_as_good_is_seen_as_code(self) -> None:
        """The taught examples are re-derived from the command text, not copied into this file.

        So a future author who adds a fifth 'Good:' example that the checker would blind itself
        to fails here, at the moment they add it.
        """
        text = BUILD_MODULE.read_text(encoding="utf-8")
        match = re.search(r"^- Good: (.+)$", text, flags=re.M)
        assert match, "build_module.md no longer shows examples of a GOOD falsifier"
        examples = [e.strip().strip("`") for e in match.group(1).split(",")]
        assert len(examples) >= 3, examples
        for example in examples:
            assert not vpnt.is_prose_line("src/a.py", f"{example} = 1"), (
                f"build_module.md teaches {example!r} as a good falsifier, but a code line "
                "starting with it is classified as prose -- so the CONTRADICTED verdict is "
                "silently downgraded to advisory for the command's own example"
            )

    @pytest.mark.parametrize("suffix", vpnt.PROSE_SUFFIXES)
    def test_every_prose_suffix_is_really_treated_as_prose(self, suffix: str) -> None:
        """A markdown/rst/txt line is prose whether or not it carries a comment marker."""
        assert vpnt.is_prose_line(f"docs/thing{suffix}", "plain sentence naming lru_cache")

    def test_a_real_code_line_still_refutes_even_beside_a_comment(self, tmp_path: Path) -> None:
        """The prose carve-out must not become an escape hatch: code outranks a comment."""
        events = write_events(tmp_path, make_record(Falsifier="lru_cache"))
        diff = make_diff(
            "scripts/guard.py", ["# lru_cache was considered", "@lru_cache(maxsize=None)"]
        )
        result = vpnt.verify(events, diff, min_changed_lines=999)
        assert result["exit_code"] == vpnt.EXIT_FAILED, (
            "a comment placed above the offending line downgraded a real refutation to advisory"
        )
        assert kinds(result) == ["CONTRADICTED"]

    def test_the_advisory_kinds_are_exactly_the_ones_that_do_not_fail_the_run(self) -> None:
        """Adding a kind without deciding its severity must fail closed, not pass silently."""
        assert "CONTRADICTED-IN-PROSE" in vpnt.ADVISORY_KINDS
        assert "UNRECORDED" in vpnt.ADVISORY_KINDS
        assert "CONTRADICTED" not in vpnt.ADVISORY_KINDS
        assert "PHANTOM" not in vpnt.ADVISORY_KINDS
        assert "UNFALSIFIABLE" not in vpnt.ADVISORY_KINDS

    def test_a_phantom_on_a_path_that_exists_names_the_untracked_cause(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The commonest false PHANTOM is a diff taken without ``--intent-to-add``."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "brand_new_xyz.py").write_text("x = 1\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        events = write_events(tmp_path, make_record(Files="src/brand_new_xyz.py"))
        result = vpnt.verify(events, make_diff("src/other.py", ["y = 1"]), min_changed_lines=999)
        problems = result["problems"]
        assert isinstance(problems, list)
        assert problems[0]["kind"] == "PHANTOM"
        assert "intent-to-add" in problems[0]["detail"], (
            "the failure text does not tell the reader that an untracked NEW file is the likely "
            "cause, so the instructed fix is to falsify a correct record"
        )

    def test_a_genuinely_absent_path_gets_no_untracked_excuse(self, tmp_path: Path) -> None:
        """The hint must not fire on a record that really is phantom."""
        events = write_events(tmp_path, make_record(Files="src/does_not_exist_anywhere_xyz.py"))
        result = vpnt.verify(events, make_diff("src/other.py", ["y = 1"]), min_changed_lines=999)
        problems = result["problems"]
        assert isinstance(problems, list)
        assert problems[0]["kind"] == "PHANTOM"
        assert "intent-to-add" not in problems[0]["detail"]


class TestDeletionsAreVisible:
    """A deletion is a decision. Before this it halted the review or refuted the record.

    Both arms use REAL ``git diff`` output, because the defect was in reading git's
    ``+++ /dev/null`` header shape and a hand-written diff could have been written to agree with
    the parser.
    """

    @staticmethod
    def _repo_with_a_deletion(root: Path) -> tuple[str, str]:
        """Build a repo, delete a file, modify another; return (mixed diff, deletion-only diff).

        Args:
            root: Directory to create the throwaway repo in (always under tmp_path).

        Returns:
            The mixed diff and the deletion-only diff, both from real git.
        """
        root.mkdir(parents=True)

        def run(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                ["git", *args], cwd=root, capture_output=True, text=True, check=True
            )

        run("init", "-q")
        run("config", "user.email", "t@example.com")
        run("config", "user.name", "t")
        (root / "src").mkdir()
        (root / "src" / "old.py").write_text(
            "\n".join(f"old{i}" for i in range(200)), encoding="utf-8"
        )
        (root / "src" / "keep.py").write_text("keep = 1\n", encoding="utf-8")
        run("add", "-A")
        run("commit", "-qm", "base")
        (root / "src" / "old.py").unlink()
        (root / "src" / "keep.py").write_text("keep = 2\n", encoding="utf-8")
        mixed = run("diff").stdout
        only = run("diff", "--", "src/old.py").stdout
        assert "+++ /dev/null" in only, "fixture is broken: git did not emit a deletion header"
        return mixed, only

    def test_a_deletion_only_diff_does_not_read_as_an_unparseable_one(
        self, tmp_path: Path
    ) -> None:
        """A well-formed git diff raised InstrumentFailureError -> exit 3 -> 'HALT'."""
        _, only = self._repo_with_a_deletion(tmp_path / "repo")
        facts = vpnt.parse_diff(only)
        assert facts.changed_lines == {"src/old.py": 200}, facts.changed_lines
        assert facts.added_by_file["src/old.py"] == [], "a deleted file cannot have added lines"

    def test_a_record_whose_decision_was_the_deletion_verifies(self, tmp_path: Path) -> None:
        """'delete it rather than keep a shim' is among the highest-value records there is."""
        mixed, _ = self._repo_with_a_deletion(tmp_path / "repo")
        events = write_events(
            tmp_path,
            make_record(
                Decision="what to do with the superseded module",
                Chosen="delete src/old.py outright",
                Rejected="keep it as a deprecation shim",
                Files="src/old.py",
                Falsifier="DeprecationWarning",
            ),
        )
        result = vpnt.verify(events, mixed, min_changed_lines=999)
        assert result["exit_code"] == vpnt.EXIT_OK, result["problems"]

    def test_a_deleted_file_counts_toward_the_coverage_proxy(self, tmp_path: Path) -> None:
        """A whole file vanishing must not be invisible to the silent-case check."""
        mixed, _ = self._repo_with_a_deletion(tmp_path / "repo")
        events = write_events(tmp_path, make_record())
        result = vpnt.verify(events, mixed, min_changed_lines=20)
        problems = result["problems"]
        assert isinstance(problems, list)
        unrecorded = [p["detail"] for p in problems if p["kind"] == "UNRECORDED"]
        assert any("src/old.py" in detail for detail in unrecorded), unrecorded


class TestAPayloadLineIsNotAFileHeader:
    """A diff line that merely LOOKS like a header must not be read as one.

    Found by probing rather than by review: a removed line beginning ``-- `` becomes ``--- `` in
    the diff and an added line beginning ``++ `` becomes ``+++ ``. Read as headers they cost the
    real file its churn (so it drops out of the coverage proxy AND out of the contradiction
    check, both silently) and register a path that does not exist. ``-- `` lines are live in this
    repo's own markdown, so this is not hypothetical here.
    """

    @staticmethod
    def _real_git_diff(root: Path) -> str:
        """Produce a real ``git diff`` whose payload contains header-shaped lines.

        Args:
            root: Directory for the throwaway repo (always under tmp_path).

        Returns:
            The diff text git actually emitted.
        """
        root.mkdir(parents=True)

        def run(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                ["git", *args], cwd=root, capture_output=True, text=True, check=True
            )

        run("init", "-q")
        run("config", "user.email", "t@example.com")
        run("config", "user.name", "t")
        (root / "doc.md").write_text("-- old sql comment\nkeep\n", encoding="utf-8")
        (root / "code.py").write_text("a = 1\n", encoding="utf-8")
        run("add", "-A")
        run("commit", "-qm", "base")
        (root / "doc.md").write_text("keep\n++ lru_cache marker line\n", encoding="utf-8")
        (root / "code.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
        diff = run("diff").stdout
        assert "\n+++ lru_cache marker line" in diff, "fixture broken: git emitted no fake header"
        assert "\n--- old sql comment" in diff, "fixture broken: git emitted no fake --- line"
        return diff

    def test_the_real_file_keeps_its_churn_and_no_phantom_path_appears(
        self, tmp_path: Path
    ) -> None:
        """Both halves of the defect, measured on real git output."""
        facts = vpnt.parse_diff(self._real_git_diff(tmp_path / "repo"))
        assert set(facts.changed_lines) == {"doc.md", "code.py"}, (
            f"a payload line was read as a file header: {sorted(facts.changed_lines)}"
        )
        assert facts.changed_lines["doc.md"] == 2, facts.changed_lines
        assert any("lru_cache marker line" in line for line in facts.added_by_file["doc.md"]), (
            "the added line was attributed to a phantom path instead of to doc.md, so no "
            "contradiction check could ever see it"
        )

    def test_a_contradiction_hiding_behind_the_fake_header_is_still_caught(
        self, tmp_path: Path
    ) -> None:
        """End to end: the swallowed line is the one that refutes the record."""
        diff = self._real_git_diff(tmp_path / "repo")
        events = write_events(
            tmp_path, make_record(Files="doc.md", Falsifier="lru_cache marker line")
        )
        result = vpnt.verify(events, diff, min_changed_lines=999)
        # doc.md is prose, so the honest verdict is the ADVISORY one -- but it must be REPORTED,
        # and before the fix nothing was reported at all because the line was attributed away.
        assert kinds(result) == ["CONTRADICTED-IN-PROSE"], result["problems"]

    def test_a_miscounted_hunk_header_still_reads_as_payload(self, tmp_path: Path) -> None:
        """Graceful degradation: the permissive fallback must not be lost with the fix.

        ``make_record``-style hand-written diffs carry ``@@ -1,1 +1,1 @@`` regardless of how many
        lines follow. Those extra lines must still be read, or every hand-written fixture (and any
        tool-generated diff with an unreadable header) silently reports less than it contains.
        """
        diff = make_diff("scripts/guard.py", [f"line{i}" for i in range(30)])
        facts = vpnt.parse_diff(diff)
        assert facts.changed_lines["scripts/guard.py"] == 30, facts.changed_lines

    def test_two_files_in_one_hand_written_diff_stay_separate(self, tmp_path: Path) -> None:
        """The fallback must not swallow the NEXT file's header and merge the two."""
        diff = make_diff("a.py", [f"l{i}" for i in range(9)]) + make_diff("b.py", ["x = 1"])
        facts = vpnt.parse_diff(diff)
        assert facts.changed_lines == {"a.py": 9, "b.py": 1}, facts.changed_lines


class TestTheThresholdJustificationIsReMeasuredNotQuoted:
    """The docstring justifies 20 with a median. A quoted number is a claim, so re-derive it."""

    def test_the_default_threshold_sits_below_this_corpus_median_churn(self) -> None:
        """Re-measures from git instead of trusting the comment beside the constant.

        Deliberately asserts the *relation* the justification rests on (the threshold is below
        the median, so a normal edit is asked to account for itself) rather than the literal
        median, which moves with every commit. Measured 2026-08-09: median 44 over the full
        history, 45 over the last 60 non-merge commits — the relation has ~2x of headroom.
        """
        shas = subprocess.run(
            ["git", "log", "--no-merges", "-60", "--format=%H"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        if len(shas) < 20:
            pytest.skip(f"shallow or young checkout ({len(shas)} commits): nothing to measure")
        numstat = subprocess.run(
            ["git", "show", "--numstat", "--format=%H", *shas],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        churn = [
            int(parts[0]) + int(parts[1])
            for parts in (line.split("\t") for line in numstat.splitlines())
            if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit()
        ]
        assert len(churn) > 100, f"too few file-touches to be meaningful: {len(churn)}"
        median = statistics.median(churn)
        assert vpnt.DEFAULT_MIN_CHANGED_LINES < median, (
            f"the coverage proxy's threshold ({vpnt.DEFAULT_MIN_CHANGED_LINES}) is no longer "
            f"below this corpus's median per-file churn ({median}), so the justification written "
            "beside the constant no longer holds: a median-sized edit now passes unspoken-for"
        )


class TestTheProseCarveOutIsSizedNotJustDisclosed:
    """CONTRADICTED — the only check of a record's TRUTH — is off for most of this corpus.

    A blind critic's finding: the limitation was disclosed in three places and quantified in
    none, while every other number in the slice carried a measurement. An unquantified limit
    reads as an edge case, and a reader of `/review` Step 6.4 would over-trust a green exit 0 on
    a markdown-only governance change — which is most of what this repo does.
    """

    @staticmethod
    def _prose_share_of_qualifying_touches() -> tuple[int, int]:
        """Re-derive (prose touches, qualifying touches) from git rather than quoting a number.

        Returns:
            How many file-touches whose churn reaches the coverage threshold are prose files,
            and how many such touches there are in total.
        """
        shas = subprocess.run(
            ["git", "log", "--no-merges", "--format=%H"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        numstat = subprocess.run(
            ["git", "show", "--numstat", "--format=%H", *shas],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        qualifying = [
            parts[2]
            for parts in (line.split("\t") for line in numstat.splitlines())
            if len(parts) == 3
            and parts[0].isdigit()
            and parts[1].isdigit()
            and int(parts[0]) + int(parts[1]) >= vpnt.DEFAULT_MIN_CHANGED_LINES
        ]
        prose = [p for p in qualifying if p.lower().endswith(vpnt.PROSE_SUFFIXES)]
        return len(prose), len(qualifying)

    def test_prose_really_is_the_majority_of_what_the_checker_looks_at(self) -> None:
        """The claim written beside PROSE_SUFFIXES and in /review Step 6.4, re-measured.

        Asserts the RELATION the disclosure rests on — prose is the majority case, so the
        contradiction check is off for most of what it would judge — rather than the literal
        64.8%, which moves with every commit. Measured 2026-08-09: 577 of 891 qualifying
        file-touches over all 143 non-merge commits.
        """
        prose, qualifying = self._prose_share_of_qualifying_touches()
        if qualifying < 100:
            pytest.skip(f"too few qualifying touches to be meaningful ({qualifying})")
        assert prose / qualifying > 0.5, (
            f"prose is now only {prose}/{qualifying} of qualifying file-touches. The disclosure "
            "beside PROSE_SUFFIXES and in /review Step 6.4 says the contradiction check is off "
            "for the MAJORITY of this corpus; that is no longer true and the wording overstates "
            "the limitation. Re-measure and rewrite both places."
        )

    def test_the_size_of_the_hole_is_stated_where_a_reviewer_reads_it(self) -> None:
        """A limit disclosed without a number is the shape of an overclaim."""
        block = REVIEW.read_text(encoding="utf-8")
        block = block[block.index("## Step 6.4") : block.index("## Step 6.5")]
        assert re.search(r"\d+(\.\d+)?%", block), (
            "/review Step 6.4 describes CONTRADICTED-IN-PROSE as advisory without quantifying "
            "how much of this repo's work it covers, so a green exit 0 on a markdown change "
            "reads as 'records verified' when nothing was checked for truth"
        )

    def test_a_markdown_only_change_cannot_produce_the_blocking_verdict(
        self, tmp_path: Path
    ) -> None:
        """The consequence of the carve-out, as an executable statement rather than a caveat."""
        events = write_events(tmp_path, make_record(Files=".claude/commands/review.md"))
        diff = make_diff(
            ".claude/commands/review.md", ["Use COMMAND_TEXT_RE to guard the command block."]
        )
        result = vpnt.verify(events, diff, min_changed_lines=999)
        assert result["exit_code"] == vpnt.EXIT_OK
        assert kinds(result) == ["CONTRADICTED-IN-PROSE"], (
            "if this now blocks, the carve-out changed and every disclosure of its size is stale"
        )


class TestTheDiffTheCommandsTakeContainsNewFiles:
    """``git diff`` never shows untracked files, and new files are what a build produces."""

    def test_git_diff_head_alone_really_does_miss_a_new_file(self, tmp_path: Path) -> None:
        """Measured, not asserted: the premise behind the prose pin below."""
        repo = tmp_path / "repo"
        repo.mkdir()

        def run(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                ["git", *args], cwd=repo, capture_output=True, text=True, check=True
            )

        run("init", "-q")
        run("config", "user.email", "t@example.com")
        run("config", "user.name", "t")
        (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
        run("add", "-A")
        run("commit", "-qm", "base")
        (repo / "src").mkdir()
        (repo / "src" / "new_module.py").write_text(
            "\n".join(f"line{i}" for i in range(40)), encoding="utf-8"
        )
        before = run("diff", "HEAD").stdout
        assert before.strip() == "", "premise broken: git diff DID show the untracked file"

        events = write_events(tmp_path, make_record(Files="src/new_module.py"))
        assert kinds(vpnt.verify(events, before)) == ["PHANTOM"], (
            "without --intent-to-add the truthful record about a NEW file is refuted"
        )

        run("add", "--intent-to-add", "--all")
        after = run("diff", "HEAD").stdout
        assert "src/new_module.py" in vpnt.parse_diff(after).changed_lines
        result = vpnt.verify(events, after, min_changed_lines=999)
        assert result["exit_code"] == vpnt.EXIT_OK, result["problems"]

    @pytest.mark.parametrize("path", [BUILD_MODULE, REVIEW])
    def test_both_commands_take_the_diff_in_a_way_that_sees_new_files(self, path: Path) -> None:
        """The RUNNABLE line must be there, not merely a comment that mentions the flag.

        This assertion was ``'--intent-to-add' in block``, which a blind critic defeated by
        mutation: deleting the actual ``git add --intent-to-add --all`` line from
        ``build_module.md`` left the whole suite green, because the explanatory comment beside it
        also contains the flag. Verified here rather than trusted — the mutation is applied to a
        COPY of the block text below, so the test proves its own failing arm without touching a
        file.
        """
        text = path.read_text(encoding="utf-8")
        blocks = re.findall(r"```bash\n(.*?)```", text, flags=re.DOTALL)
        # Only blocks that actually hand the checker a DIFF are in scope. `--list-sources` reads
        # Layer 1 and no diff at all, so demanding `--intent-to-add` there would be a guard that
        # fires on a block it cannot be about.
        invoking = [b for b in blocks if "verify_paths_not_taken.py" in b and "--diff" in b]
        assert invoking, f"{path.name} no longer pipes a diff into the checker in a bash block"

        def has_the_command(block: str) -> bool:
            return any(
                line.strip().startswith("git add") and "--intent-to-add" in line
                for line in block.splitlines()
            )

        for block in invoking:
            assert has_the_command(block), (
                f"{path.name} pipes a diff into scripts/verify_paths_not_taken.py without a "
                "runnable `git add --intent-to-add ...` line in the same block. A COMMENT "
                "mentioning the flag does not satisfy this and must not: measured, an untracked "
                "40-line module gives `git diff HEAD` of 0 bytes, so every record naming a NEW "
                "file is falsely reported PHANTOM and the command then tells the builder to "
                "rewrite a true record."
            )
            without_the_command = "\n".join(
                line for line in block.splitlines() if not line.strip().startswith("git add")
            )
            assert not has_the_command(without_the_command), (
                "this guard is satisfied by something other than the command line, which is the "
                "exact defect it was rewritten to fix"
            )


class TestTheCapturedFindingIsActuallyClassifiable:
    """A severity marker the extractor does not parse is a finding filed at the wrong tier."""

    def test_every_severity_marker_in_review_is_one_the_extractor_parses(self) -> None:
        """Measured through the live classifier, not against a list copied into this file."""
        import extract_findings  # noqa: PLC0415 -- local so ruff cannot autofix it away

        text = REVIEW.read_text(encoding="utf-8")
        found = re.findall(r"Severity:\s*(\S+)([^\"\n]*)", text)
        # `Severity: <tier>` (line 443) is a placeholder telling specialists to substitute a
        # tier, not a marker /review itself writes. Angle-bracket placeholders are the only
        # exemption; a literal word is always checked.
        markers = [(word, tail) for word, tail in found if not word.startswith("<")]
        assert len(markers) >= 3, (
            "/review no longer prescribes concrete severity markers for the path-not-taken "
            f"findings (found {found!r})"
        )
        for word, tail in markers:
            line = f"Severity: {word}{tail}"
            assert extract_findings._EXPLICIT_SEVERITY_RE.search(line) is not None, (
                f"/review prescribes the severity marker {word!r}, which "
                "scripts/extract_findings.py does not recognise. The event still becomes a "
                "finding, but at whatever tier the keyword heuristic guesses -- measured, "
                "'blocking' lands at 'medium', i.e. BELOW must-fix."
            )
            assert extract_findings._classify_severity(line) == word.lower(), (
                f"the marker {word!r} does not classify as {word.lower()!r}"
            )

    def test_the_blocking_kind_is_filed_above_the_uncheckable_one(self) -> None:
        """The two tiers must actually differ, or the distinction in the prose is decoration."""
        import extract_findings  # noqa: PLC0415

        high = extract_findings._classify_severity("Severity: HIGH - record refuted")
        medium = extract_findings._classify_severity("Severity: MEDIUM - record is uncheckable")
        assert (high, medium) == ("high", "medium")


class TestTheStepIsDefinedForEveryWorkflowShape:
    """The most frequent review in this repo is the small change, which has no discussion."""

    def test_the_small_change_path_is_routed_rather_than_left_undefined(self) -> None:
        """``--discussion`` on an id that does not resolve is exit 3, i.e. HALT."""
        text = REVIEW.read_text(encoding="utf-8")
        block = text[text.index("## Step 6.4") : text.index("## Step 6.5")]
        assert "NOT RUN" in block, (
            "Step 6.4 is mandatory but says nothing about the 1-2 file workflow, which has no "
            "/plan or /build_module discussion. The nearest wrong answer (pass an id and hope) "
            "raises InstrumentFailureError -> exit 3 -> HALT."
        )
        assert "small-change" in block or "small change" in block

    def test_an_unresolvable_discussion_id_really_is_an_instrument_failure(self) -> None:
        """The reason the routing sentence has to exist, measured."""
        with pytest.raises(vpnt.InstrumentFailureError):
            vpnt.resolve_discussion_events("DISC-00000000-000000-does-not-exist")


class TestTheMechanismHasAWorkingEntryPoint:
    """`/review` cannot check records it cannot find, and NOT RUN is the frictionless answer.

    A blind critic named this as the mechanism's only entry point and found it unwired: nothing
    produced or discovered the `/plan` and `/build_module` discussion ids, so
    ``verifier_exit_code: NOT RUN`` — documented, honest-sounding, zero effort — was the path of
    least resistance for every build-driven review. A check whose skip costs nothing is prose.
    These tests pin BOTH halves of the fix: the ids are handed over by the builder, and they are
    recoverable by the reviewer when they were not.
    """

    @staticmethod
    def _tree(root: Path, *, date: str, disc: str, content: str) -> Path:
        """Plant one discussion under a fake ``discussions/`` root (always in tmp_path).

        Args:
            root: The fake discussions root.
            date: Date-directory name.
            disc: Discussion id.
            content: Event content to write.

        Returns:
            The discussion directory created.
        """
        disc_dir = root / date / disc
        disc_dir.mkdir(parents=True)
        write_events(disc_dir, content)
        return disc_dir

    def test_a_discussion_holding_records_is_discoverable(self, tmp_path: Path) -> None:
        """The reviewer can find the ids nobody handed over."""
        root = tmp_path / "discussions"
        self._tree(root, date="2026-08-09", disc="build-thing", content=make_record())
        assert vpnt.find_record_sources(root) == [("2026-08-09", "build-thing", 1)]

    def test_a_discussion_with_no_records_is_not_listed(self, tmp_path: Path) -> None:
        """Listing every discussion would bury the two that matter."""
        root = tmp_path / "discussions"
        self._tree(root, date="2026-08-09", disc="chatty", content="no blocks here")
        assert vpnt.find_record_sources(root) == []

    def test_the_listing_is_newest_first_and_counts_records(self, tmp_path: Path) -> None:
        """Order and count are what make the list usable without opening files."""
        root = tmp_path / "discussions"
        self._tree(root, date="2026-08-01", disc="plan-old", content=make_record())
        newer = root / "2026-08-09" / "build-new"
        newer.mkdir(parents=True)
        write_events(newer, make_record(), make_record(Decision="second"))
        assert vpnt.find_record_sources(root) == [
            ("2026-08-09", "build-new", 2),
            ("2026-08-01", "plan-old", 1),
        ]

    def test_one_corrupt_discussion_does_not_kill_the_listing(self, tmp_path: Path) -> None:
        """A listing that dies on an old malformed file helps nobody find anything."""
        root = tmp_path / "discussions"
        self._tree(root, date="2026-08-09", disc="good", content=make_record())
        bad = root / "2026-08-08" / "broken"
        bad.mkdir(parents=True)
        (bad / "events.jsonl").write_text("{not json\n", encoding="utf-8")
        assert vpnt.find_record_sources(root) == [("2026-08-09", "good", 1)]
        # ...but the REAL verification pass over that same file must still refuse to be silent.
        with pytest.raises(vpnt.InstrumentFailureError):
            vpnt.verify(bad / "events.jsonl", make_diff("a.py", ["x = 1"]))

    def test_the_listing_does_not_auto_select(self, tmp_path: Path) -> None:
        """Auto-selecting every discussion would refute old TRUE records against today's diff.

        Measured here rather than argued: an unrelated older record, checked against a diff that
        does not touch its files, is a blocking PHANTOM. That is why discovery lists and the
        caller chooses.
        """
        root = tmp_path / "discussions"
        old = self._tree(
            root, date="2026-01-01", disc="plan-unrelated", content=make_record(Files="src/old.py")
        )
        result = vpnt.verify(old / "events.jsonl", make_diff("src/new.py", ["x = 1"]))
        assert result["exit_code"] == vpnt.EXIT_FAILED
        assert kinds(result) == ["PHANTOM"]

    def test_the_cli_exposes_the_listing_and_names_the_empty_case(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Through ``main``, because a helper no CLI reaches is not an entry point."""
        root = tmp_path / "discussions"
        root.mkdir()
        monkeypatch.setattr(vpnt, "DISCUSSIONS_DIR", root)
        assert vpnt.main(["--list-sources"]) == vpnt.EXIT_OK
        empty = capsys.readouterr().out
        assert "no discussion" in empty.lower(), empty

        self._tree(root, date="2026-08-09", disc="build-thing", content=make_record())
        assert vpnt.main(["--list-sources"]) == vpnt.EXIT_OK
        listed = capsys.readouterr().out
        assert "build-thing" in listed and "2026-08-09" in listed, listed

    def test_list_sources_needs_no_diff_but_verification_still_does(self, tmp_path: Path) -> None:
        """Relaxing --diff for the listing must not let a real run pass with no diff at all."""
        events = write_events(tmp_path, make_record())
        with pytest.raises(SystemExit) as excinfo:
            vpnt.main(["--events", str(events)])
        assert excinfo.value.code != vpnt.EXIT_OK

    def test_review_runs_discovery_before_it_may_write_not_run(self) -> None:
        """Structural: the escape hatch must sit AFTER the command that removes its excuse."""
        text = REVIEW.read_text(encoding="utf-8")
        block = text[text.index("## Step 6.4") : text.index("## Step 6.5")]
        assert "--list-sources" in block, (
            "/review Step 6.4 no longer tells the reviewer how to FIND the discussions holding "
            "records. Without a lookup, `NOT RUN` is the zero-effort answer to every review and "
            "the step is decoration."
        )
        # Anchored on the hand-off KEY rather than on a sentence: `verifier_exit_code` is part of
        # the Step 7 contract this file already pins, so it moves only if the contract moves.
        assert block.index("--list-sources") < block.index("verifier_exit_code: NOT RUN"), (
            "the discovery command was moved below the instruction that writes "
            "`verifier_exit_code: NOT RUN`, so a reader meets the escape hatch before the thing "
            "that removes its excuse"
        )

    def test_the_not_run_value_has_to_quote_what_discovery_returned(self) -> None:
        """A skip nobody has to justify is a skip that becomes the default."""
        text = REVIEW.read_text(encoding="utf-8")
        block = text[text.index("## Step 6.4") : text.index("## Step 6.5")]
        not_run_para = block[block.index("NOT RUN") : block.index("NOT RUN") + 900]
        assert "--list-sources" in not_run_para, (
            "`NOT RUN` may again be written without reporting the discovery result, so 'nobody "
            "gave me the ids' survives as a reason after the listing made it checkable"
        )

    def test_build_module_hands_the_discussion_id_to_the_reviewer(self) -> None:
        """The asymmetry the critic found: /plan stated its id, /build_module did not."""
        text = BUILD_MODULE.read_text(encoding="utf-8")
        summary = text[text.index("## Step 8: Present Build Summary") :]
        assert "discussion_id" in summary, (
            "/build_module's build summary lists the records and the exit code but never the "
            "discussion id that carries them, so /review has no handle on them and falls back "
            "to NOT RUN. /plan Step 7 states its id; this side must too."
        )
        assert "--discussion" in summary or "verify_paths_not_taken" in summary, (
            "the summary names an id without saying what consumes it, which is how a required "
            "hand-off gets dropped as noise"
        )

    def test_plan_still_hands_over_its_own_id(self) -> None:
        """The half that already worked must not regress while the other half is fixed."""
        text = PLAN.read_text(encoding="utf-8")
        assert re.search(r"discussion id", text, flags=re.I), (
            "/plan no longer tells the developer the discussion id carrying its spec-time records"
        )


class TestTheAntiVacuityNoteReachesTheModeReviewRuns:
    """``/review`` invokes ``--json``; a note only ``_render`` prints is absent right there."""

    def test_the_note_is_in_the_result_payload_not_only_in_the_rendering(
        self, tmp_path: Path
    ) -> None:
        """The payload is what a --json caller reads."""
        events = write_events(tmp_path, "no blocks here")
        result = vpnt.verify(events, make_diff("a.py", ["x = 1"]), min_changed_lines=999)
        assert result["note"] == vpnt.VACUOUS_NOTE
        assert "asserted almost nothing" in vpnt._render(result)

    def test_a_non_vacuous_run_carries_no_note(self, tmp_path: Path) -> None:
        """The note must mean something; a note on every run is a note nobody reads."""
        events = write_events(tmp_path, make_record())
        result = vpnt.verify(events, make_diff("scripts/guard.py", ["ok = 1"]))
        assert result["note"] == ""

    def test_the_json_cli_emits_the_note_where_a_caller_will_see_it(self, tmp_path: Path) -> None:
        """Through the real CLI, in the exact mode /review uses."""
        events = write_events(tmp_path, "no blocks here")
        diff_path = tmp_path / "c.diff"
        diff_path.write_text(make_diff("a.py", ["x = 1"]), encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/verify_paths_not_taken.py"),
                "--events",
                str(events),
                "--diff",
                str(diff_path),
                "--min-changed-lines",
                "999",
                "--json",
            ],
            capture_output=True,
            text=True,
            cwd=tmp_path,
        )
        assert proc.returncode == vpnt.EXIT_OK, proc.stdout + proc.stderr
        payload = json.loads(proc.stdout)
        assert "asserted almost nothing" in payload["note"]
        assert "asserted almost nothing" in proc.stderr, (
            "a --json run that checked nothing printed a bare green payload; the one sentence "
            "that stops 'checked nothing' reading as 'verified clean' must not require the "
            "caller to dig it out of the payload"
        )


class TestThisGuardsOwnCitations:
    """Claims this module makes about other files are claims, and rot like any other."""

    def test_framework_paths_is_defined_where_the_module_docstring_says(self) -> None:
        """The docstring previously cited change_package.py, which only mentions it in prose."""
        manifest = REPO_ROOT / "scripts/lineage/manifest.py"
        text = manifest.read_text(encoding="utf-8")
        assert re.search(r"^FRAMEWORK_PATHS", text, flags=re.M), (
            "FRAMEWORK_PATHS is no longer DEFINED in scripts/lineage/manifest.py; this module's "
            "propagation warning cites the wrong file again"
        )
        assert chr(34) + ".claude/" + chr(34) in text
        assert chr(34) + "scripts/" + chr(34) in text
        assert chr(34) + "tests/" + chr(34) not in text, (
            "tests/ is now in FRAMEWORK_PATHS, so this module DOES travel to derived projects "
            "and the standing limitation in the docstring is stale"
        )


# ---------------------------------------------------------------------------
# 7. The coverage proxy is TUNED, and the tuning is measured in both directions
# ---------------------------------------------------------------------------


def _git_repo(root: Path) -> tuple[Path, object]:
    """Make a throwaway git repo with one commit, and return it with a runner.

    Args:
        root: Directory to create (always under ``tmp_path``).

    Returns:
        The repo path and a ``run(*args)`` helper that shells out to git inside it.
    """
    root.mkdir(parents=True)

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True)

    run("init", "-q")
    run("config", "user.email", "t@example.com")
    run("config", "user.name", "t")
    run("config", "core.autocrlf", "false")
    (root / "seed.txt").write_bytes(b"seed\n")
    run("add", "-A")
    run("commit", "-qm", "base")
    return root, run


class TestTheCoverageProxyIsTunedNotJustDocumented:
    """Case 3 is the SILENT case, so its signal-to-noise is the whole of its value.

    A blind critic's finding: shipped with no default exclude set, exit 2 was the ordinary
    verdict — measured over the last 30 non-merge commits, 155 file-touches crossed the churn
    threshold, median 3.5 per commit, and the largest single source was SELF-INFLICTED, because
    ``discussions/`` grows precisely when a builder writes path-not-taken records. An advisory
    that fires every run stops being read.

    These tests pin the tuning from BOTH sides: the set really filters (so it is not decoration),
    and it does NOT reach a product path (so nobody later "fixes" a noisy exit 2 by excluding the
    tree the proxy exists to ask about).
    """

    @staticmethod
    def _noisy_diff() -> str:
        """A diff touching one bookkeeping path and one product path, both above threshold.

        Returns:
            Unified diff text.
        """
        return make_diff(
            "discussions/2026-08-09/DISC-x/events.jsonl", [f"{{}}{i}" for i in range(30)]
        ) + make_diff("src/product.py", [f"line{i}" for i in range(30)])

    def test_the_default_set_is_applied_when_the_caller_passes_nothing(
        self, tmp_path: Path
    ) -> None:
        """The failing arm of the finding: without this, Layer 1 is reported unspoken-for."""
        events = write_events(tmp_path, make_record(Files="src/product.py"))
        result = vpnt.verify(events, self._noisy_diff(), min_changed_lines=20)
        unrecorded = [
            p["detail"]
            for p in result["problems"]  # type: ignore[union-attr]
            if p["kind"] == "UNRECORDED"
        ]
        assert not unrecorded, (
            f"a bookkeeping path was reported unspoken-for: {unrecorded}. DEFAULT_EXCLUDES is "
            "not being applied, so exit 2 is again the ordinary verdict"
        )
        assert result["exit_code"] == vpnt.EXIT_OK

    def test_the_self_inflicted_layer_one_loop_is_the_one_that_had_to_close(self) -> None:
        """Writing MORE records must not make your own events.jsonl the thing that is flagged."""
        assert any(
            fnmatch_ok("discussions/2026-08-09/DISC-build/events.jsonl", pattern)
            for pattern in vpnt.DEFAULT_EXCLUDES
        ), (
            "discussions/ is no longer excluded from the coverage proxy. Layer 1 grows BECAUSE "
            "the builder wrote path-not-taken records, so the proxy now penalises the exact "
            "behaviour this whole mechanism exists to encourage"
        )

    def test_an_empty_exclude_list_means_none_rather_than_the_default(
        self, tmp_path: Path
    ) -> None:
        """``None`` and ``[]`` must be distinguishable, or the default cannot be opted out of."""
        events = write_events(tmp_path, make_record(Files="src/product.py"))
        result = vpnt.verify(events, self._noisy_diff(), min_changed_lines=20, excludes=[])
        assert "UNRECORDED" in kinds(result), (
            "excludes=[] still applied the default set, so a caller cannot ask the unfiltered "
            "question and the default is unfalsifiable"
        )

    def test_the_filtering_is_reported_rather_than_silent(self, tmp_path: Path) -> None:
        """A default exclusion nobody can see reads like a proxy that quietly stopped asking."""
        events = write_events(tmp_path, make_record(Files="src/product.py"))
        result = vpnt.verify(events, self._noisy_diff(), min_changed_lines=20)
        assert result["excluded_files"] == 1, result
        rendered = vpnt._render(result)
        assert "skipped by an exclude glob" in rendered, (
            "the run does not say it filtered anything, so a reader cannot tell a clean coverage "
            "result from a proxy that was told not to look"
        )

    @pytest.mark.parametrize(
        "path",
        [
            "src/telemetry/model.py",
            "scripts/quality_gate.py",
            ".claude/commands/review.md",
            "tests/test_paths_not_taken.py",
            "docs/adr/ADR-0099-something.md",
            "docs/sprints/SPEC-20260809-x.md",
            "config/gate_profiles.yaml",
            "CLAUDE.md",
        ],
    )
    def test_the_default_set_never_swallows_a_path_that_can_hold_a_decision(
        self, path: str
    ) -> None:
        """The over-broadening guard, and it is the more important direction.

        ``tests/`` and ``docs/adr`` + ``docs/sprints`` are named explicitly because they are the
        tempting next entries: ``tests/*`` alone would take the measured median from 3.0 to 2.0.
        They are kept in scope because "a test file cannot hold a design decision" is false in
        this repo — this module's own header records choosing relation-assertions over literal
        ones — and because an ADR or a spec is where a decision is SUPPOSED to land.
        """
        hit = [g for g in vpnt.DEFAULT_EXCLUDES if fnmatch_ok(path, g)]
        assert not hit, (
            f"{path} is excluded from the coverage proxy by {hit}. That is not tuning, it is "
            "switching off case 3 for a tree whose files can carry a real decision"
        )

    def test_the_measured_noise_reduction_is_re_derived_from_git(self) -> None:
        """The 155 -> 111 claim beside DEFAULT_EXCLUDES, re-measured instead of quoted.

        Asserts the RELATION the justification rests on (the set removes a material share of the
        qualifying touches, and the share it removes is bookkeeping rather than most of the
        corpus) rather than the literal counts, which move with every commit. Measured
        2026-08-09 over the last 30 non-merge commits: 155 -> 111, a 28.4% cut.
        """
        shas = subprocess.run(
            ["git", "log", "--no-merges", "-30", "--format=%H"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        if len(shas) < 20:
            pytest.skip(f"shallow or young checkout ({len(shas)} commits): nothing to measure")
        numstat = subprocess.run(
            ["git", "show", "--numstat", "--format=%H", *shas],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        qualifying = [
            parts[2]
            for parts in (line.split("\t") for line in numstat.splitlines())
            if len(parts) == 3
            and parts[0].isdigit()
            and parts[1].isdigit()
            and int(parts[0]) + int(parts[1]) >= vpnt.DEFAULT_MIN_CHANGED_LINES
        ]
        if len(qualifying) < 50:
            pytest.skip(f"too few qualifying touches to be meaningful ({len(qualifying)})")
        kept = [p for p in qualifying if not any(fnmatch_ok(p, g) for g in vpnt.DEFAULT_EXCLUDES)]
        removed = len(qualifying) - len(kept)
        assert removed / len(qualifying) > 0.15, (
            f"DEFAULT_EXCLUDES now removes only {removed}/{len(qualifying)} qualifying "
            "file-touches. The measurement written beside the constant no longer holds -- "
            "either the corpus changed or the set was narrowed; re-measure and rewrite it."
        )
        assert removed / len(qualifying) < 0.60, (
            f"DEFAULT_EXCLUDES now removes {removed}/{len(qualifying)} qualifying file-touches. "
            "Past roughly half the corpus this is no longer noise-tuning: the coverage proxy has "
            "been switched off for most of what it would ask about, which is the failure this "
            "set was added to avoid on the other side."
        )

    @pytest.mark.parametrize("path", [REVIEW, BUILD_MODULE])
    def test_both_commands_state_the_filtering_they_now_inherit(self, path: Path) -> None:
        """A reader of exit 2 must know which paths were never asked about.

        Pinned as cross-file AGREEMENT with the constant, not as a sentence: every glob in
        ``DEFAULT_EXCLUDES`` has to appear in the command that reads the exit code, so narrowing
        or widening the set without touching the prose fails here.
        """
        text = path.read_text(encoding="utf-8")
        missing = [g for g in vpnt.DEFAULT_EXCLUDES if g not in text]
        assert not missing, (
            f"{path.name} branches on the coverage proxy but never says {missing} are skipped "
            "before it runs. A filtered exit 2 that reads as unfiltered overstates coverage."
        )

    def test_the_cli_can_ask_the_unfiltered_question(self, tmp_path: Path) -> None:
        """Through the real entry point: the default must be an opt-out, not a hard-coding."""
        events = write_events(tmp_path, make_record(Files="src/product.py"))
        diff_path = tmp_path / "c.diff"
        diff_path.write_text(self._noisy_diff(), encoding="utf-8")
        argv = [
            sys.executable,
            str(REPO_ROOT / "scripts/verify_paths_not_taken.py"),
            "--events",
            str(events),
            "--diff",
            str(diff_path),
        ]
        filtered = subprocess.run(argv, capture_output=True, text=True, cwd=tmp_path)
        unfiltered = subprocess.run(
            [*argv, "--no-default-excludes"], capture_output=True, text=True, cwd=tmp_path
        )
        assert filtered.returncode == vpnt.EXIT_OK, filtered.stdout + filtered.stderr
        assert unfiltered.returncode == vpnt.EXIT_COVERAGE_GAP, (
            "--no-default-excludes did not restore the unfiltered question, so the default set "
            "cannot be checked by the person it filters for"
        )


def fnmatch_ok(path: str, pattern: str) -> bool:
    """Match a path against one exclude glob exactly as the checker does.

    Defined here rather than imported so the test states the matching rule it relies on --
    ``fnmatch``'s ``*`` crosses ``/``, which is why ``discussions/*`` covers the whole subtree.

    Args:
        path: Repo-relative path.
        pattern: One entry from :data:`verify_paths_not_taken.DEFAULT_EXCLUDES`.

    Returns:
        Whether the coverage proxy would skip this path for this pattern.
    """
    return fnmatch.fnmatch(path, pattern)


class TestTheNewFileFigureIsBoundToWhatProducesIt:
    """A quoted measurement must be re-derivable from the shape the sentence names.

    A blind critic's finding: the commands and the script's docstring quoted "488 bytes" for the
    diff a new 40-line file produces, and the figure is not a property of the shape named beside
    it. In a slice whose thesis is that a self-reported claim must be checkable against evidence,
    a number bound to the wrong path is the exact defect class it exists to stop.
    """

    @staticmethod
    def _new_file_diff(root: Path, rel: str, trailing: bool) -> tuple[int, int]:
        """Add a 40-line untracked file, then measure the diff it produces after ``-N``.

        Args:
            root: Directory for the throwaway repo (under ``tmp_path``).
            rel: Repo-relative path to create.
            trailing: Whether the file ends with a newline.

        Returns:
            ``(byte length of the diff, insertions reported by --numstat)``.
        """
        repo, run = _git_repo(root)
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        body = "\n".join(f"line{i}" for i in range(40)) + ("\n" if trailing else "")
        target.write_bytes(body.encode())
        assert run("diff", "HEAD").stdout == "", (
            "premise broken: git diff showed the untracked file without --intent-to-add"
        )
        run("add", "--intent-to-add", "--all")
        diff = run("diff", "HEAD").stdout
        numstat = run("diff", "HEAD", "--numstat").stdout.strip().split("\t")
        return len(diff.encode()), int(numstat[0])

    def test_the_insertion_count_is_stable_where_a_byte_size_is_not(self, tmp_path: Path) -> None:
        """The executable reason the byte figure was dropped rather than re-bound."""
        shapes = [
            ("src/new_module.py", True),
            ("src/new_module.py", False),
            ("new_module.py", True),
            ("new_module.py", False),
        ]
        measured = [
            self._new_file_diff(tmp_path / f"r{i}", rel, trailing)
            for i, (rel, trailing) in enumerate(shapes)
        ]
        sizes = {m[0] for m in measured}
        inserts = {m[1] for m in measured}
        assert inserts == {40}, (
            f"the insertion count is not stable across path/trailing-newline shapes: {measured}. "
            "The commands quote it precisely because it was."
        )
        assert len(sizes) > 1, (
            f"every shape produced the same diff size {sizes}, so a byte figure would have been "
            "safe to quote after all and this guard's premise is stale -- re-measure before "
            "putting one back"
        )

    def test_build_module_quotes_the_figure_this_test_derives(self, tmp_path: Path) -> None:
        """Cross-check the prose against a measurement instead of against another sentence."""
        _, insertions = self._new_file_diff(tmp_path / "bm", "src/new_module.py", trailing=False)
        text = BUILD_MODULE.read_text(encoding="utf-8")
        block = next(
            b
            for b in re.findall(r"```bash\n(.*?)```", text, flags=re.DOTALL)
            if "--intent-to-add" in b
        )
        # The PAIR is what is asserted, inside one window. Asserting the two figures separately
        # was defeated by mutation: the block's own `commit -am` warning also contains the words
        # "40 insertions", so replacing the after-figure with "a non-empty diff" left this green.
        paired = re.search(r"0 bytes[\s\S]{0,200}?(\d+) insertions", block)
        assert paired, (
            "build_module.md no longer states the before/after pair ('0 bytes' -> 'N insertions') "
            "in one breath. The pair IS the argument for the mandatory --intent-to-add line; "
            "either half alone does not make it."
        )
        assert int(paired.group(1)) == insertions, (
            f"build_module.md quotes {paired.group(1)} insertions where a real `git add "
            f"--intent-to-add` on a 40-line new file produces {insertions}"
        )


class TestTheIntentToAddLineIsBounded:
    """``git add --intent-to-add --all`` is a `--all` verb a Required skill prohibits by name.

    A blind critic's finding: both commands mandate it as a MANDATORY first line while
    ``.claude/skills/committing-changes/SKILL.md`` Step 1.8 (Required) says never ``git add -A`` /
    ``git add .`` with an entangled tree. It is not a correctness bug -- ``-N`` stages no content
    -- but the reassurance was incomplete, and the gap is a real one measured below.
    """

    def test_commit_dash_a_after_intent_to_add_really_does_commit_the_file(
        self, tmp_path: Path
    ) -> None:
        """The hazard the added sentence names, measured rather than asserted.

        Without this the warning is superstition, and a superstition is the first instruction a
        builder drops.
        """
        repo, run = _git_repo(tmp_path / "hazard")
        (repo / "src").mkdir()
        (repo / "src" / "new_module.py").write_bytes(
            "\n".join(f"line{i}" for i in range(40)).encode()
        )
        run("add", "--intent-to-add", "--all")
        assert run("diff", "--cached", "--numstat").stdout == "", (
            "`-N` staged content; the commands' claim that it stages none is wrong"
        )
        plain = subprocess.run(
            ["git", "commit", "-m", "x"], cwd=repo, capture_output=True, text=True
        )
        assert plain.returncode != 0, (
            "`git commit -m` after `-N` created a commit; the 'stages no content' claim relies "
            "on it refusing"
        )
        dash_a = subprocess.run(
            ["git", "commit", "-am", "x"], cwd=repo, capture_output=True, text=True
        )
        assert dash_a.returncode == 0 and "40 insertions" in dash_a.stdout, (
            "`git commit -am` after `-N` no longer commits the intent-to-add'ed file. If that is "
            "really git's behaviour now, the warning in both commands is stale -- do not delete "
            "it without re-measuring on the git version the commands ship against"
        )

    @pytest.mark.parametrize("path", [REVIEW, BUILD_MODULE])
    def test_the_command_bounds_the_verb_it_mandates(self, path: Path) -> None:
        """Relation, not a sentence: the two obligations must both be present near the line.

        (1) ``commit -a`` must be named as the thing that turns ``-N`` into a real commit, and
        (2) the explicit-staging rule must be pointed at, so the reader does not read a MANDATORY
        ``--all`` as permission to stage that way.
        """
        text = path.read_text(encoding="utf-8")
        block = next(
            b
            for b in re.findall(r"```bash\n(.*?)```", text, flags=re.DOTALL)
            if any(
                line.strip().startswith("git add") and "--intent-to-add" in line
                for line in b.splitlines()
            )
        )
        assert re.search(r"commit -a", block), (
            f"{path.name} mandates `git add --intent-to-add --all` without naming `git commit -a` "
            "as the follow-up that commits it in full. Measured: after `-N`, `commit -m` refuses "
            "but `commit -am` commits the file with 40 insertions."
        )
        assert "1.8" in block or "committing-changes" in block, (
            f"{path.name} mandates a `--all` staging verb without pointing at the Required rule "
            "that prohibits `git add -A` / `git add .`, so the two read as contradicting each "
            "other and a reader resolves it by ignoring one of them"
        )


class TestTheScriptDoesNotClaimAutomaticEnforcement:
    """The script's own docstring may not claim Principle #2 while nothing invokes it.

    Attached as a condition to the Steward's APPROVE (2026-08-09). An earlier draft of
    ``scripts/verify_paths_not_taken.py`` opened by naming Principle #2 — *capture is automatic,
    enforced by scripts and hooks and not by instruction* — as what the file delivers, and
    described itself as "the part that does not depend on an agent choosing to be diligent".
    ``ADR-0034`` retracted that in three places. The script did not, so the two documents said
    opposite things about the same fact: exactly the cross-file drift the rest of this module
    exists to catch, living in the file this module guards.

    The guard is bidirectional on purpose, so it dies with its reason rather than outliving it:

    * While **no caller exists**, the docstring must not assert Principle #2, and must carry the
      measurement that shows why.
    * The moment someone **does** wire it — a quality-gate check, a hook, a ``settings.json``
      entry — ``test_the_no_caller_measurement_still_holds`` goes RED and asks for the docstring
      to be re-derived. Wiring it would make the Principle #2 claim *true*, and a guard that
      forbade the claim forever would then be enforcing a stale fact.

    What it cannot do: it reads text and counts callers. It cannot tell whether a caller that
    exists is actually reached at runtime.
    """

    #: Surfaces where a real invocation could live. Markdown is deliberately excluded — an
    #: instruction to run a script is the thing being distinguished FROM a caller, and treating
    #: prose as wiring is the error this class exists to name.
    EXECUTABLE_SURFACES = (
        "scripts/**/*.py",
        ".claude/hooks/**/*",
        ".claude/settings.json",
        "config/**/*",
        "pyproject.toml",
    )

    @staticmethod
    def _callers() -> list[str]:
        """Return every reference to the script that is WIRING rather than PROSE.

        The prose/wiring distinction is the whole substance of this helper, and the first
        version of it did not make the distinction at all — it was a bare
        ``"verify_paths_not_taken" in text`` over whole files. Two independent reviewers
        caught it on 2026-08-09, within hours, on a comment added to
        ``config/model_context_profiles.yaml`` by an unrelated re-measurement: a dated note
        citing the script BY NAME while discussing its coverage proxy. The guard reported a
        caller that did not exist, and because the quality gate runs pytest, the branch failed
        its own new test.

        That failure mode is worse than a missed defect. A guard that cries wolf is the first
        thing a future builder mutes — and this is the guard protecting the honesty of the
        Principle #2 retraction, so muting it is exactly how the false claim comes back.

        The irony is recorded rather than tidied away: ``verify_paths_not_taken.py`` — the very
        script this class guards — already solves this with ``is_prose_line()``, and its own
        module docstring calls prose-vs-code *"the direction that matters most"*. The guard did
        not copy the one idea from the file it was written to protect.

        Limits, stated because the fix must not be trusted further than it goes: this strips
        whole-line ``#`` comments only. A trailing comment on a code line, a block comment in a
        format that has one, or a mention inside a string literal would still read as wiring.
        That direction is deliberate — it over-reports rather than under-reports, and an
        over-report is a loud failure a human resolves, while an under-report silently blesses
        a false Principle #2 claim.
        """
        script = (REPO_ROOT / "scripts" / "verify_paths_not_taken.py").resolve()
        hits: list[str] = []
        for pattern in TestTheScriptDoesNotClaimAutomaticEnforcement.EXECUTABLE_SURFACES:
            for path in REPO_ROOT.glob(pattern):
                if not path.is_file() or path.resolve() == script:
                    continue
                if path.suffix == ".md":
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                code = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
                if any("verify_paths_not_taken" in ln for ln in code):
                    hits.append(str(path.relative_to(REPO_ROOT)).replace("\\", "/"))
        return sorted(hits)

    #: An *affirmative* claim of Principle #2 — the file asserting it delivers automatic
    #: enforcement. Deliberately NOT a search for the bare string "Principle #2": the honest
    #: docstring must name the principle in order to deny it, and the denial paragraph is dense
    #: with words like "rather than" and "nothing invokes".
    #:
    #: RECORDED BECAUSE THE FIRST VERSION OF THIS GUARD WAS GREEN UNDER ITS OWN MUTATION.
    #: It searched for any mention and accepted a denial token anywhere within 240 characters.
    #: Replacing "It is not Principle #2" with "It is Principle #2" left it passing, because the
    #: surrounding paragraph still contained "rather than" and "nothing invokes". That is this
    #: module's own subject — a check that measures a property adjacent to the one it claims —
    #: committed by the check itself. It is written down rather than quietly corrected, because
    #: the fix is only worth trusting if the reader knows the first attempt was not.
    AFFIRMATIVE_CLAIM = re.compile(
        r"(?:is|are|delivers|satisfies|implements|provides|achieves|means)\s+"
        r"(?:the\s+)?Principle\s*#\s*2",
        re.IGNORECASE,
    )
    NEGATION_BEFORE = re.compile(r"\b(not|never|n't|no longer|rather than)\b\s*$", re.IGNORECASE)

    @staticmethod
    def _module_docstring() -> str:
        doc = vpnt.__doc__
        assert doc, "scripts/verify_paths_not_taken.py has no module docstring to check"
        return doc

    def test_the_no_caller_measurement_still_holds(self) -> None:
        """If this fails, the script gained a caller — re-derive the docstring, don't mute it."""
        callers = self._callers()
        assert not callers, (
            f"scripts/verify_paths_not_taken.py now has non-markdown caller(s): {callers}. "
            "That is a real change in what the file delivers — wiring it makes the Principle #2 "
            "claim TRUE. Re-derive the module docstring's 'What this file is NOT' section against "
            "the new wiring (and update ADR-0034's retraction) rather than deleting this test."
        )

    def test_principle_2_is_only_ever_mentioned_to_deny_it(self) -> None:
        """Relation, not a literal: every mention must sit inside a denial, however worded."""
        doc = self._module_docstring()
        mentions = [m.start() for m in re.finditer(r"Principle #2", doc)]
        assert mentions, (
            "the module docstring no longer mentions Principle #2 at all. The denial is "
            "load-bearing — a reader who meets this file first must be told it is NOT "
            "automatic enforcement. Restore it as a denial, do not drop it."
        )
        del mentions  # presence is asserted above; the real check is on affirmative CLAIMS
        for match in self.AFFIRMATIVE_CLAIM.finditer(doc):
            preceding = doc[max(0, match.start() - 40) : match.start()]
            assert self.NEGATION_BEFORE.search(preceding), (
                "the module docstring makes an AFFIRMATIVE Principle #2 claim with no negation "
                f"immediately before it: ...{doc[max(0, match.start() - 90) : match.end() + 40]!r}"
                "... Nothing invokes this script (see the no-caller test in this class), so "
                "that claim is false here and contradicts ADR-0034's retraction."
            )

    def test_the_docstring_carries_the_measurement_not_just_the_assertion(self) -> None:
        """The denial must show its work — this repo's standard is measure, never assert."""
        doc = self._module_docstring()
        assert "grep" in doc, (
            "the module docstring denies Principle #2 but does not carry the command that "
            "proves it. 'Nothing invokes this' is a measurable claim; quote the grep."
        )
        assert re.search(r"no caller|nothing invokes|zero", doc, re.IGNORECASE), (
            "the docstring quotes a command but never states its result in words a reader can "
            "check against the output"
        )

    def test_it_names_the_smaller_property_it_does_deliver(self) -> None:
        """Denying #2 without naming #3 would read as 'this script is worthless'. It is not."""
        doc = self._module_docstring()
        assert "Principle #3" in doc, (
            "the docstring retracts Principle #2 without naming what the script DOES buy: "
            "Principle #3 — the record is written by the builder and re-run by a separate "
            "context that did not write it, against the diff rather than against the story."
        )


class TestTheIntentToAddIsReversed:
    """`-N` mutates the index. The instruction that undoes it must survive editing.

    SPEC-20260812-122753 R2 closed REV-20260809-222916 Advisory 3 (HIGH) by mandating a
    reversal beside both ``git add --intent-to-add --all`` lines. Two blind reviewers
    independently noted that the slice shipping that mandate pinned the *pointer prose* around
    it and left the mandate itself unguarded: ``git grep "git reset" -- tests/`` returned
    nothing, so a later editor could simplify the scoped form to a bare ``git reset`` — the one
    form measured to silently unstage unrelated work — with a green suite.

    Shaped like the sibling :class:`TestTheIntentToAddLineIsBounded`: a relation inside the
    fence, not a fixed sentence, so rewording is free and losing the guarantee is not.
    """

    @staticmethod
    def _fence(path: Path) -> str:
        """The ```bash fence holding the ``--intent-to-add`` mandate."""
        return next(
            b
            for b in re.findall(r"```bash\n(.*?)```", path.read_text(encoding="utf-8"), re.DOTALL)
            if any(
                line.strip().startswith("git add") and "--intent-to-add" in line
                for line in b.splitlines()
            )
        )

    @staticmethod
    def _commands(fence: str) -> list[str]:
        """Runnable lines only. A ``#`` line documents the hazard; it does not perform it."""
        return [
            line.strip()
            for line in fence.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

    @pytest.mark.regression
    @pytest.mark.parametrize("path", [REVIEW, BUILD_MODULE])
    def test_the_fence_reverses_what_it_registers(self, path: Path) -> None:
        """`-N` without a reversal leaves the index redefined for every later command."""
        commands = self._commands(self._fence(path))
        assert any(c.startswith("git reset -q -- ") for c in commands), (
            f"{path.name} mandates `git add --intent-to-add --all` and never undoes it. "
            "Advisory 3 (HIGH, REV-20260809-222916) is re-opened by deleting this line: the "
            "registered paths stay in the index, where `git stash` carries them and an "
            "explicit scoped `git add` runs against a redefined untracked set."
        )

    @pytest.mark.regression
    @pytest.mark.parametrize("path", [REVIEW, BUILD_MODULE])
    def test_the_reversal_is_never_the_unscoped_form(self, path: Path) -> None:
        """Measured: the bare form and ``-- .`` both reset the WHOLE index."""
        commands = self._commands(self._fence(path))
        offenders = [
            c
            for c in commands
            if re.match(r"git reset\b", c) and not re.match(r"git reset -q -- \S", c)
        ]
        assert not offenders, (
            f"{path.name}'s reversal is unscoped: {offenders}. Measured on a throwaway repo "
            "with a sibling change staged before `-N`: both `git reset -q` and "
            "`git reset -q -- .` left `git diff --cached --numstat` EMPTY, silently discarding "
            "staged work unrelated to this check. Only a real pathspec is safe here."
        )

    @pytest.mark.regression
    @pytest.mark.parametrize("path", [REVIEW, BUILD_MODULE])
    def test_the_deletion_hazard_is_named(self, path: Path) -> None:
        """``--all`` stages worktree DELETIONS, which a ``??``-scoped reset cannot reach.

        Measured on a throwaway repo: with ``  D sibling.txt`` present, after `-N` the index
        carried ``0\t1\tsibling.txt``; a reset scoped to the ``??`` paths left it there; and a
        plain ``git commit -m`` — no ``-a`` anywhere — committed the unrelated deletion. The
        fence's ``commit -a`` warning does not cover that path, so the hazard must be named.
        """
        fence = self._fence(path)
        assert re.search(r"\bD\b[\s\S]{0,400}?(delet|DELET)", fence) or re.search(
            r"(delet|DELET)[\s\S]{0,400}?\bD\b", fence
        ), (
            f"{path.name}'s intent-to-add fence no longer tells the runner that `--all` stages "
            "tracked-file DELETIONS as well as registering untracked paths. Without it the "
            "capture step looks like it only needs the `??` lines, the reversal misses the "
            "staged deletion, and a plain `git commit -m` ships it."
        )
