"""Tests for surfacing the education-gate deferral backlog in the SessionStart hook.

WHAT IS COVERED HERE
--------------------
1. ``backlog_summary`` — the rendering itself: age bucketing, escalation marker,
   ``re-deferred`` inclusion, unparseable dates, and the empty case.
2. The ``backlog`` CLI subcommand — including its two failure arms (missing registry,
   corrupt YAML), which must print one diagnostic line and still exit 0, because the
   only caller is a SessionStart hook that must never break a session.
3. The hook <-> CLI contract, asserted three ways:
   - the hook text actually invokes the ``backlog`` subcommand;
   - the hook is a READER (it names no mutating subcommand and no write cmdlet against
     ``gates.yaml``) — ``docs/education/CONTRACTS.md`` §4 declares ``gates.yaml`` has
     exactly one writer, and a review finding (M3) already flagged a second writer as a
     defect requiring a ``contract_version`` bump;
   - end-to-end: the hook is executed under the interpreter ``settings.json`` actually
     configures (``powershell`` = Windows PowerShell 5.1) and its stdout must contain
     the exact lines ``backlog_summary`` produces for the live registry. That test fails
     if either side drifts. Its comparison lives in ``_check_hook_matches_rendering`` and
     is itself unit-tested in both directions (``TestHookMatchChecker``), because the
     nothing-owed branch is unreachable while the live registry has open gates — which is
     precisely how a vacuous assertion survives a review.
4. That surfacing this backlog is NOT a build condition: ``scripts/quality_gate.py``
   must contain no education-gate check. ``docs/education/governance-mechanisms.md``
   Row 6 rules that turning Principle #5 into a build condition needs its own /plan and
   a Steward gate, so this test pins the informational-only boundary.
5. That the documented ``clear`` command does not destroy the registry's comment header.
   ``yaml.safe_dump`` cannot round-trip comments, so before ``read_header`` was added the
   first ``clear`` took the header to zero lines. (Reproduced 2026-08-09 against commit
   ``31bfe09``: that commit's 16-line header went to 0. The command is in
   ``read_header``'s docstring; the git-free pin is
   ``tests/test_gate_registry.py::TestHeaderPreservation``.) Since the nudge names
   ``clear``, shipping it without that fix would have made following the framework's own
   advice silently destructive.
6. That the nudge asks for the right thing: the action that CLOSES a gate (an education
   session) is named before the bookkeeping that RECORDS one, and the commands it names
   exist as files. ``clear_gate`` validates neither ``--session-id`` nor ``--discussion-id``
   against any store, so a ``clear``-first nudge would be an invitation to fabricate a
   zero-debt registry.
7. That the debt this change leaves in ``docs/education/governance-mechanisms.md`` (out of
   scope here, three sentences now false) stays paired with the notes acknowledging it —
   ``test_governance_doc_debt_and_its_acknowledgement_stay_in_sync``. A debt recorded only
   in a code comment is the same look-if-you-remember control the doc itself indicts.

WHAT IS **NOT** COVERED, AND WHY
--------------------------------
- The hook-execution tests skip on any non-Windows platform and whenever
  ``powershell`` is absent from PATH. On such a machine, nothing here executes the
  ``.ps1`` at all — only the python side is exercised.
- **Nothing here proves the hook ever runs in a real session.** The nudge appears only when
  the hook runs, and which SessionStart events run it is set by the matcher in
  .claude/settings.json — a protected file, out of scope for this change, with the required
  edit reported separately. Measured 2026-08-09 that matcher was ``resume|compact``, so the
  backlog surfaced on resume/compaction but not on a fresh session.

  The settings-facing test here is deliberately **matcher-agnostic**
  (``test_settings_still_wires_the_session_start_hook``): it asserts only that SessionStart
  still runs ``session-start.ps1`` at all, which is the failure that would actually silence
  the nudge. An earlier revision asserted ``matchers == ["resume|compact"]``, which turned
  RED the moment the developer applied the very edit this slice asks him to apply.

  Drift in the *prose* is caught by two tests with deliberately different powers, because a
  previous revision claimed one test had both:
    - ``test_prose_points_at_the_live_matcher`` is a **presence** check. It requires every
      file describing the surfacing to carry ``MATCHER_POINTER``. It cannot detect a false
      sentence added alongside that pointer, and does not claim to.
    - ``test_prose_makes_no_unqualified_session_start_claim`` is the **negative** check that
      does. It finds every sentence making a timing claim about session start and requires
      a qualifier in the same sentence. It is a heuristic over a fixed trigger vocabulary
      (``_TIMING_CLAIM_TRIGGERS``), not a proof of honesty — it catches the phrasings named
      there and nothing else — and the heuristic itself is pinned by
      ``test_session_start_claim_checker_is_itself_correct``.
- The "python not on PATH" arm IS exercised, by
  ``test_hook_degrades_cleanly_when_python_is_not_on_path``, which re-runs the hook in a
  child process whose PATH is cut down to the Windows system directories. Measured
  2026-08-09: exit 0, zero stderr, the education line silently absent, and the other six
  PROCESS HEALTH lines still printed. It skips wherever the PowerShell tests skip.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from scripts.education.gate_registry import (
    BACKLOG_ESCALATION_DAYS,
    CLEAR_COMMAND_HINT,
    LEARN_COMMAND_HINT,
    UNCLOSED_STATUSES,
    backlog_summary,
    build_parser,
    load_registry,
    main,
    read_header,
    save_registry,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "scripts" / "education" / "gate_registry.py"
HOOK_PATH = PROJECT_ROOT / ".claude" / "hooks" / "session-start.ps1"
LIVE_REGISTRY = PROJECT_ROOT / "docs" / "education" / "gates.yaml"
SETTINGS_PATH = PROJECT_ROOT / ".claude" / "settings.json"
QUALITY_GATE = PROJECT_ROOT / "scripts" / "quality_gate.py"

TODAY = date(2026, 8, 8)

#: The one sentence every file describing the surfacing must carry. It POINTS AT the
#: matcher instead of asserting a value, so it stays true whatever the matcher is set to
#: -- including after the developer applies the edit reported in out_of_scope_needed.
MATCHER_POINTER = "which SessionStart events run it is set by the matcher in .claude/settings.json"

#: SessionStart event tokens observed in vendored third-party configs (see
#: ``test_settings_matcher_uses_only_recognised_event_tokens`` for the exact sources).
#: Evidence, not a spec -- no official harness documentation is readable from this repo.
KNOWN_SESSION_START_EVENTS = frozenset({"startup", "resume", "clear", "compact"})

#: Files that describe when the backlog is surfaced, and so must carry MATCHER_POINTER.
PROSE_FILES = (
    HOOK_PATH,
    MODULE_PATH,
    LIVE_REGISTRY,
    Path(__file__).resolve(),
)

#: PROSE_FILES minus this test module, for the unqualified-claim check. This module is
#: excluded because it contains the banned phrasings by construction, as the fixtures of
#: ``test_session_start_claim_checker_is_itself_correct``. Excluding it is a real gap in
#: coverage of this file's own prose, stated rather than hidden: whether it passed would
#: otherwise depend on where sentence-splitting happened to land inside a fixture list.
#: The mechanism files -- the ones a reader consults to learn when the backlog surfaces --
#: are all still checked.
CLAIM_CHECKED_FILES = (HOOK_PATH, MODULE_PATH, LIVE_REGISTRY)

#: Phrases that make a claim about WHEN the surfacing happens. A sentence containing one of
#: these must also contain a qualifier, or it is asserting a schedule the matcher decides.
#: Deliberately excludes bare "SessionStart hook", which names the hook without claiming a
#: schedule. This is a fixed vocabulary, not a parser: it catches these phrasings only.
#: "fresh session" is listed only in its claim-shaped forms: the hook's unrelated
#: pre-existing "This may be a fresh session." (about a missing BUILD_STATUS.md) is not a
#: claim about when anything surfaces, and a checker that flagged it would train its reader
#: to ignore it.
_TIMING_CLAIM_TRIGGERS = (
    "at session start",
    "on session start",
    "every session",
    "each session",
    "on a fresh session",
    "every fresh session",
    "any session",
)

#: Words that make a timing sentence honest: it points at the matcher, names the events the
#: matcher actually selects, or negates/limits the claim.
_TIMING_CLAIM_QUALIFIERS = (
    "matcher",
    "settings.json",
    "resume",
    "compact",
    "not ",
    "never",
    "only",
)

#: Greppable token marking the debt this change leaves in a file it may not edit.
OWED_DEBT_TOKEN = "OWED-DEBT: docs/education/governance-mechanisms.md Row 6"

#: The path that debt is owed to, and the sentences in it this change falsified.
GOVERNANCE_DOC = PROJECT_ROOT / "docs" / "education" / "governance-mechanisms.md"
GOVERNANCE_DOC_STALE_SENTENCES = (
    "Nothing **warns** either.",
    "Nothing notices.",
    "Visibility that depends on somebody choosing to look is the weakest",
)

#: Files carrying the acknowledgement of that debt.
OWED_DEBT_FILES = (HOOK_PATH, MODULE_PATH)

_HAVE_POWERSHELL = sys.platform == "win32" and shutil.which("powershell") is not None
requires_powershell = pytest.mark.skipif(
    not _HAVE_POWERSHELL,
    reason="Windows PowerShell (the interpreter settings.json configures) is not available",
)


def _prose(text: str) -> str:
    """Flatten a file's text so one sentence can be matched across line/comment breaks.

    Joins wrapped lines and drops leading ``#`` comment markers, so the same sentence
    matches whether it lives in a PowerShell comment, a YAML comment, or a docstring.

    Args:
        text: Raw file text.

    Returns:
        The text as a single whitespace-normalised line.
    """
    return re.sub(r"\s+", " ", re.sub(r"\n[ \t]*#?[ \t]*", " ", text))


def _unqualified_session_start_claims(text: str) -> list[str]:
    """Return sentences that claim WHEN the backlog surfaces without qualifying it.

    A sentence qualifies if it mentions the matcher or settings.json, names the events the
    matcher currently selects, or negates/limits the claim. "The backlog is surfaced at
    session start" is unqualified and is returned; "the hook does not run on every session:
    ... is set by the matcher in .claude/settings.json" is not.

    Sentences are split on a period/question/exclamation **followed by whitespace**, so
    ``.claude/settings.json`` and ``gate_registry.py`` do not split a sentence in two.

    This is a fixed-vocabulary heuristic (:data:`_TIMING_CLAIM_TRIGGERS` /
    :data:`_TIMING_CLAIM_QUALIFIERS`), not a general honesty proof. It catches the listed
    phrasings; a novel one gets through.

    Args:
        text: Raw file text.

    Returns:
        The offending sentences, in order.
    """
    prose = _prose(text)
    offenders = []
    for sentence in re.split(r"(?<=[.!?])\s+", prose):
        lowered = sentence.lower()
        if not any(trigger in lowered for trigger in _TIMING_CLAIM_TRIGGERS):
            continue
        if any(qualifier in lowered for qualifier in _TIMING_CLAIM_QUALIFIERS):
            continue
        offenders.append(sentence.strip())
    return offenders


def _join_path_arg_count(rest: str) -> int:
    """Count the top-level arguments of a ``Join-Path`` call.

    ``rest`` is the text following the ``Join-Path`` token on its line. Parenthesised
    sub-expressions count as one argument; the scan stops at a ``)`` that closes an
    enclosing group, or at a pipe/statement separator.

    Args:
        rest: Line text after the ``Join-Path`` token.

    Returns:
        The number of top-level arguments.
    """
    depth = 0
    count = 0
    in_token = False
    quote = ""
    for char in rest:
        if quote:
            if char == quote:
                quote = ""
            continue
        if char in "\"'":
            quote = char
            if not in_token:
                in_token = True
                count += 1
            continue
        if char == "(":
            depth += 1
            if not in_token:
                in_token = True
                count += 1
            continue
        if char == ")":
            if depth == 0:
                break
            depth -= 1
            continue
        if depth > 0:
            continue
        if char in " \t":
            in_token = False
        elif char in "|;":
            break
        elif not in_token:
            in_token = True
            count += 1
    return count


def _check_hook_matches_rendering(stdout_lines: list[str], candidates: list[list[str]]) -> None:
    """Assert hook stdout agrees with ``backlog_summary``, in BOTH directions.

    A non-empty rendering must appear verbatim in stdout. An empty one (nothing owed) is
    not a free pass: stdout must then contain no education line at all. The earlier version
    of this check was ``all(line in stdout for line in expected)`` inline, which is
    vacuously True over an empty ``expected`` — so the pin would have gone quiet at exactly
    the moment the developer cleared the last gate.

    Lives here as a function rather than inline so both branches are reachable from unit
    tests (``TestHookMatchChecker``) without needing a live registry in either state.

    Args:
        stdout_lines: The hook's stdout, split into lines.
        candidates: Renderings that would be acceptable (one per plausible "today").

    Raises:
        AssertionError: If stdout matches no candidate, or nags with nothing owed.
    """
    non_empty = [expected for expected in candidates if expected]
    if non_empty:
        matched = [
            expected for expected in non_empty if all(line in stdout_lines for line in expected)
        ]
        assert matched, (
            f"hook output matched no candidate rendering; candidates={non_empty!r} "
            f"stdout_lines={stdout_lines[:40]!r}"
        )
        return
    offenders = [line for line in stdout_lines if "EDUCATION DEBT" in line]
    assert offenders == [], f"nothing is owed but the hook still nagged: {offenders}"


def _gate(
    gate_id: str,
    created_at: str,
    status: str = "open",
) -> dict[str, Any]:
    """Return a valid gate mapping with the given id/date/status."""
    cleared_by = None
    if status == "cleared":
        cleared_by = {
            "session_id": "QUIZ-1",
            "discussion_id": "DISC-1",
            "cleared_at": "2026-06-11T00:00:00+00:00",
        }
    return {
        "gate_id": gate_id,
        "created_at": created_at,
        "origin": "REV-20260610-012629",
        "scope": {"files": [], "adrs": [], "spec": None},
        "reason_deferred": "deferred to next interactive session",
        "status": status,
        "cleared_by": cleared_by,
    }


def _registry(*gates: dict[str, Any]) -> dict[str, Any]:
    """Return a valid registry wrapping the given gates."""
    return {"version": 1, "gates": list(gates)}


# --------------------------------------------------------------------------- #
# backlog_summary — the rendering
# --------------------------------------------------------------------------- #
class TestBacklogSummary:
    def test_empty_registry_is_silent(self) -> None:
        assert backlog_summary(_registry(), today=TODAY) == []

    def test_all_cleared_is_silent(self) -> None:
        reg = _registry(_gate("EDU-a", "2026-01-01", status="cleared"))
        assert backlog_summary(reg, today=TODAY) == []

    def test_open_gate_produces_exactly_four_lines(self) -> None:
        reg = _registry(_gate("EDU-a", "2026-06-10"))
        lines = backlog_summary(reg, today=TODAY)
        assert len(lines) == 4

    def test_every_line_is_indented_for_the_process_health_block(self) -> None:
        reg = _registry(_gate("EDU-a", "2026-06-10"))
        for line in backlog_summary(reg, today=TODAY):
            assert line.startswith("  "), line

    def test_every_line_is_a_single_line(self) -> None:
        """The hook prints one line per signal; an embedded newline would wreck the block."""
        reg = _registry(_gate("EDU-a", "2026-06-10"))
        for line in backlog_summary(reg, today=TODAY):
            assert "\n" not in line and "\r" not in line, repr(line)

    def test_headline_names_count_oldest_age_and_oldest_id(self) -> None:
        reg = _registry(
            _gate("EDU-new", "2026-08-01"),
            _gate("EDU-oldest", "2026-06-10"),
            _gate("EDU-mid", "2026-07-01"),
        )
        headline = backlog_summary(reg, today=TODAY)[0]
        assert "3 education gate(s)" in headline
        assert "oldest 59 days" in headline  # 2026-06-10 -> 2026-08-08
        assert "EDU-oldest" in headline

    def test_second_line_quotes_the_oldest_gates_reason(self) -> None:
        """The brief's 'useful, not just a count' requirement: WHAT is owed, not just how many.

        The registry already carries a human-readable ``reason_deferred``; a gate id like
        ``EDU-20260610-unit-3-3`` is not a decision input for a non-coding gatekeeper.
        """
        reg = _registry(_gate("EDU-new", "2026-08-01"), _gate("EDU-oldest", "2026-06-10"))
        reg["gates"][1]["reason_deferred"] = "TEMPORAL retry-chain heuristic walkthrough"
        reg["gates"][0]["reason_deferred"] = "something much newer"
        owed = backlog_summary(reg, today=TODAY)[1]
        assert "TEMPORAL retry-chain heuristic walkthrough" in owed
        assert "something much newer" not in owed

    def test_reason_is_truncated_to_one_readable_line(self) -> None:
        reg = _registry(_gate("EDU-a", "2026-06-10"))
        reg["gates"][0]["reason_deferred"] = "x" * 500
        owed = backlog_summary(reg, today=TODAY)[1]
        assert owed.endswith('..."')
        assert len(owed) < 200, len(owed)

    def test_reason_newlines_cannot_break_the_hook_block(self) -> None:
        """``reason_deferred`` is free text crossing into a hook's line-oriented stdout."""
        reg = _registry(_gate("EDU-a", "2026-06-10"))
        reg["gates"][0]["reason_deferred"] = "line one\nline two\r\n\tline three"
        lines = backlog_summary(reg, today=TODAY)
        assert len(lines) == 4
        assert lines[1] == '      It owes: "line one line two line three"'

    def test_missing_reason_does_not_produce_an_empty_quote(self) -> None:
        reg = _registry(_gate("EDU-a", "2026-06-10"))
        reg["gates"][0]["reason_deferred"] = ""
        owed = backlog_summary(reg, today=TODAY)[1]
        assert '""' not in owed
        assert "no reason_deferred" in owed

    def test_learning_action_comes_before_the_clear_bookkeeping(self) -> None:
        """`clear` must not be the nudge's headline call-to-action.

        ``clear_gate`` writes ``--session-id``/``--discussion-id`` through as opaque strings
        and checks them against nothing, so a ``clear``-first nudge asks the reader to type
        the one command that can report zero education debt with zero education done. The
        line that CLOSES a gate is the education session; ``clear`` only records it.
        """
        reg = _registry(_gate("EDU-a", "2026-06-10"))
        lines = backlog_summary(reg, today=TODAY)
        learn_index = next(i for i, line in enumerate(lines) if LEARN_COMMAND_HINT in line)
        clear_index = next(i for i, line in enumerate(lines) if CLEAR_COMMAND_HINT in line)
        assert learn_index < clear_index, lines
        assert "cannot replace one" in lines[clear_index]

    def test_action_line_still_names_the_clear_command(self) -> None:
        """Demoted, not dropped: the exact command remains discoverable from the nudge."""
        lines = backlog_summary(_registry(_gate("EDU-a", "2026-06-10")), today=TODAY)
        assert any(CLEAR_COMMAND_HINT in line for line in lines)
        assert any("clear --gate-id" in line for line in lines)

    def test_nudge_only_names_commands_that_exist(self) -> None:
        """A nudge pointing at a command that is not there is worse than no nudge.

        Asserts the command FILES exist, not their contents: their wording belongs to
        whoever maintains them, but a rename or deletion must turn this red.
        """
        for command in ("walkthrough", "quiz"):
            assert f"/{command}" in LEARN_COMMAND_HINT
            path = PROJECT_ROOT / ".claude" / "commands" / f"{command}.md"
            assert path.is_file(), f"nudge names /{command} but {path} does not exist"

    @pytest.mark.parametrize(
        ("age_days", "expected_marker"),
        [
            (BACKLOG_ESCALATION_DAYS + 1, "[!]"),
            (BACKLOG_ESCALATION_DAYS, "[i]"),
            (BACKLOG_ESCALATION_DAYS - 1, "[i]"),
            (0, "[i]"),
        ],
    )
    def test_marker_escalates_strictly_over_the_threshold(
        self, age_days: int, expected_marker: str
    ) -> None:
        created = date.fromordinal(TODAY.toordinal() - age_days)
        reg = _registry(_gate("EDU-a", created.isoformat()))
        assert backlog_summary(reg, today=TODAY)[0].startswith(f"  {expected_marker} ")

    def test_over_threshold_count_is_reported(self) -> None:
        reg = _registry(
            _gate("EDU-old-1", "2026-06-10"),
            _gate("EDU-old-2", "2026-06-27"),
            _gate("EDU-fresh", "2026-08-07"),
        )
        assert f"2 over {BACKLOG_ESCALATION_DAYS} days." in backlog_summary(reg, today=TODAY)[0]

    def test_re_deferred_gates_are_counted_not_hidden(self) -> None:
        """A re-deferred gate is unclosed debt; querying only `open` would hide it."""
        reg = _registry(_gate("EDU-a", "2026-06-10", status="re-deferred"))
        lines = backlog_summary(reg, today=TODAY)
        assert lines, "a re-deferred gate must still surface"
        assert "1 education gate(s)" in lines[0]
        assert "1 re-deferred." in lines[0]

    def test_unclosed_statuses_matches_the_status_enum_complement(self) -> None:
        """UNCLOSED_STATUSES must stay 'everything that is not cleared'."""
        from scripts.education.gate_registry import VALID_STATUSES

        assert set(UNCLOSED_STATUSES) == set(VALID_STATUSES) - {"cleared"}

    def test_unparseable_created_at_does_not_crash(self) -> None:
        reg = _registry(_gate("EDU-bad", "not-a-date"))
        lines = backlog_summary(reg, today=TODAY)
        assert len(lines) == 4
        assert "1 education gate(s)" in lines[0]
        assert "No parseable created_at" in lines[0]

    def test_unparseable_dates_still_name_a_focus_gate_and_its_reason(self) -> None:
        """With no ages there is no 'oldest', but the reader still gets a specific gate."""
        reg = _registry(_gate("EDU-bad", "not-a-date"))
        reg["gates"][0]["reason_deferred"] = "the one thing owed"
        lines = backlog_summary(reg, today=TODAY)
        assert "EDU-bad" in lines[0]
        assert "the one thing owed" in lines[1]

    def test_mixed_parseable_and_unparseable_dates(self) -> None:
        reg = _registry(_gate("EDU-good", "2026-06-10"), _gate("EDU-bad", "whenever"))
        lines = backlog_summary(reg, today=TODAY)
        assert "2 education gate(s)" in lines[0]
        assert "oldest 59 days (EDU-good)" in lines[0]
        assert "1 with unparseable created_at." in lines[0]

    def test_non_string_created_at_is_survived(self) -> None:
        """A hand-edited registry can hold a non-string date; rendering must not raise.

        The strict validator rejects this shape, but ``backlog_summary`` is also called
        on registries the hook did not validate itself, so it degrades instead.
        """
        reg = _registry(_gate("EDU-a", "2026-06-10"))
        reg["gates"][0]["created_at"] = 20260610  # type: ignore[assignment]
        lines = backlog_summary(reg, today=TODAY)
        assert len(lines) == 4
        assert "No parseable created_at" in lines[0]

    def test_non_string_reason_is_survived(self) -> None:
        """Same tolerance as created_at: a hand-edited registry must not crash the hook."""
        reg = _registry(_gate("EDU-a", "2026-06-10"))
        reg["gates"][0]["reason_deferred"] = ["not", "a", "string"]  # type: ignore[assignment]
        lines = backlog_summary(reg, today=TODAY)
        assert len(lines) == 4
        assert "no reason_deferred" in lines[1]

    def test_datetime_created_at_is_accepted(self) -> None:
        reg = _registry(_gate("EDU-a", "2026-06-10T12:00:00+00:00"))
        assert "oldest 59 days" in backlog_summary(reg, today=TODAY)[0]

    def test_defaults_to_today_when_not_given(self) -> None:
        """The default must be the local current date -- proven without a midnight race.

        Reading ``date.today()`` twice around the call and accepting either rendering
        keeps this deterministic across a day rollover. Asserting against a single
        ``date.today()`` read would fail spuriously at 00:00, which is exactly when this
        framework's autonomous overnight sessions run.
        """
        reg = _registry(_gate("EDU-a", "2026-06-10"))
        before = date.today()
        actual = backlog_summary(reg)
        after = date.today()
        assert actual in (
            backlog_summary(reg, today=before),
            backlog_summary(reg, today=after),
        )

    def test_rendering_does_not_mutate_the_registry(self) -> None:
        reg = _registry(_gate("EDU-a", "2026-06-10"))
        before = json.dumps(reg, sort_keys=True)
        backlog_summary(reg, today=TODAY)
        assert json.dumps(reg, sort_keys=True) == before


# --------------------------------------------------------------------------- #
# CLI — including the failure arms the hook depends on
# --------------------------------------------------------------------------- #
class TestBacklogCli:
    def test_backlog_is_a_registered_subcommand(self) -> None:
        args = build_parser().parse_args(["backlog"])
        assert args.command == "backlog"

    def test_cli_prints_the_same_lines_as_the_library(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = tmp_path / "gates.yaml"
        reg = _registry(_gate("EDU-a", "2026-06-10"))
        save_registry(reg, path)
        rc = main(["--registry", str(path), "backlog", "--today", TODAY.isoformat()])
        assert rc == 0
        out = capsys.readouterr().out.rstrip("\n").split("\n")
        assert out == backlog_summary(reg, today=TODAY)

    def test_cli_is_silent_when_nothing_is_owed(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = tmp_path / "gates.yaml"
        save_registry(_registry(_gate("EDU-a", "2026-06-10", status="cleared")), path)
        rc = main(["--registry", str(path), "backlog"])
        assert rc == 0
        assert capsys.readouterr().out == ""

    def test_missing_registry_is_exit_0_with_one_diagnostic(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = main(["--registry", str(tmp_path / "nope.yaml"), "backlog"])
        assert rc == 0
        out = capsys.readouterr().out
        assert out.startswith("  [?] Education gate registry unreadable")
        assert "FileNotFoundError" in out
        assert len(out.rstrip("\n").split("\n")) == 2

    def test_corrupt_yaml_is_exit_0_with_one_diagnostic(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = tmp_path / "gates.yaml"
        path.write_text("gates: [unclosed\n  bad: : :\n", encoding="utf-8")
        rc = main(["--registry", str(path), "backlog"])
        assert rc == 0
        out = capsys.readouterr().out.rstrip("\n").split("\n")
        assert len(out) == 2, "a multi-line YAML error must not leak into the hook block"
        assert out[0].startswith("  [?] Education gate registry unreadable")

    def test_schema_violation_is_exit_0_with_one_diagnostic(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = tmp_path / "gates.yaml"
        path.write_text("version: 1\ngates:\n  - gate_id: bad\n", encoding="utf-8")
        rc = main(["--registry", str(path), "backlog"])
        assert rc == 0
        assert capsys.readouterr().out.startswith("  [?] Education gate registry unreadable")

    def test_bad_today_argument_still_returns_handled_exit_2(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = tmp_path / "gates.yaml"
        save_registry(_registry(_gate("EDU-a", "2026-06-10")), path)
        rc = main(["--registry", str(path), "backlog", "--today", "not-a-date"])
        assert rc == 2
        assert "error:" in capsys.readouterr().err

    def test_subprocess_end_to_end_against_the_live_registry(self) -> None:
        """The exact invocation shape the hook uses must exit 0 and never write stderr."""
        result = subprocess.run(
            [
                sys.executable,
                str(MODULE_PATH),
                "--registry",
                str(LIVE_REGISTRY),
                "backlog",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert result.stderr == ""


# --------------------------------------------------------------------------- #
# Hook <-> CLI contract
# --------------------------------------------------------------------------- #
class TestHookContract:
    @pytest.mark.parametrize(
        ("snippet", "expected"),
        [
            (' $PWD "docs" "sprints"', 3),
            (' $PWD "memory" "decisions" "retro-action-registry.md"', 4),
            (' (Join-Path $PWD "docs") "sprints"', 2),
            (' $sharedMemory "universal-warnings.md"', 2),
            (" $PWD $dir", 2),
            (" $a $b)) {", 2),
        ],
    )
    def test_join_path_arg_counter_is_itself_correct(self, snippet: str, expected: int) -> None:
        """Pins the heuristic, so a broken counter cannot silently pass every line."""
        assert _join_path_arg_count(snippet) == expected

    def test_hook_invokes_the_backlog_subcommand(self) -> None:
        text = HOOK_PATH.read_text(encoding="utf-8")
        assert "gate_registry.py" in text
        invocations = [
            line.strip()
            for line in text.splitlines()
            if re.search(r"&\s+python\b.*\bbacklog\b", line.split("#", 1)[0])
        ]
        assert len(invocations) == 1, f"expected exactly one backlog invocation, got {invocations}"

    def test_hook_never_writes_the_registry(self) -> None:
        """CONTRACTS.md §4: gates.yaml has exactly ONE writer. The hook is not it."""
        text = HOOK_PATH.read_text(encoding="utf-8")
        gate_block = text[text.index("# 9. Education gate backlog") :]
        for mutating in (
            " add ",
            " clear ",
            " re-defer ",
            "Set-Content",
            "Out-File",
            "Add-Content",
        ):
            assert mutating not in gate_block, f"hook must not mutate the registry: {mutating!r}"

    def test_hook_uses_only_two_argument_join_path(self) -> None:
        """Windows PowerShell 5.1 (what settings.json invokes) has no 3+-arg Join-Path.

        Measured 2026-08-08: before this was fixed the hook emitted 198 stderr lines
        under 5.1 (39 naming Join-Path) and the PROCESS HEALTH block produced exactly
        one line, which was false. This is a static heuristic (it strips everything
        after the first ``#`` on a line, so a ``#`` inside a string literal would
        confuse it); the executable proof is
        ``test_hook_runs_clean_under_the_configured_interpreter``.
        """
        offenders = []
        for lineno, line in enumerate(HOOK_PATH.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            for match in re.finditer(r"Join-Path", code):
                argc = _join_path_arg_count(code[match.end() :])
                if argc > 2:
                    offenders.append(f"{HOOK_PATH.name}:{lineno} ({argc} args)")
        assert offenders == [], f"pwsh-7-only Join-Path form: {offenders}"

    @requires_powershell
    def test_hook_runs_clean_under_the_configured_interpreter(self) -> None:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(HOOK_PATH),
            ],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert result.stderr.strip() == "", result.stderr[:2000]

    @requires_powershell
    def test_hook_degrades_cleanly_when_python_is_not_on_path(self) -> None:
        """The hook must never break a session, even with no python interpreter.

        The design constraint for this check is the same one the sqlite3 promotion-candidate
        check already meets: a missing binary is a clean no-op, not a stack trace. Measured
        2026-08-09 with PATH cut to the Windows system directories: exit 0, zero stderr,
        the education line absent, the rest of the block intact.
        """
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        env = dict(os.environ)
        env["PATH"] = os.pathsep.join(
            [
                os.path.join(system_root, "System32"),
                os.path.join(system_root, "System32", "WindowsPowerShell", "v1.0"),
            ]
        )
        assert shutil.which("python", path=env["PATH"]) is None, "PATH was not reduced"

        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(HOOK_PATH)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        assert result.returncode == 0, result.stderr[:2000]
        assert result.stderr.strip() == "", result.stderr[:2000]
        assert "EDUCATION DEBT" not in result.stdout
        assert "=== PROCESS HEALTH ===" in result.stdout

    @requires_powershell
    def test_hook_stdout_contains_the_library_rendering_verbatim(self) -> None:
        """End-to-end pin: hook output must equal what backlog_summary() produces.

        The hook computes its own ``date.today()`` in a child process and takes no
        ``--today``, so the expected rendering is computed for BOTH the date read before
        the spawn and the date read after it, and the hook must match one of them. A
        single date read here would false-fail across a midnight boundary.

        Both worlds are asserted, so this pin cannot self-disable. A previous revision
        used ``all(line in stdout for line in expected)``, which is vacuously True over an
        empty expected rendering: the moment the developer cleared the last gate — the very
        moment the framework worked — the assert would have passed while testing nothing.
        Here, an empty rendering switches to the complementary assertion (the hook must
        print NO education line), which is equally falsifiable.
        """
        registry = load_registry(LIVE_REGISTRY)
        before = date.today()
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(HOOK_PATH),
            ],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        after = date.today()
        assert result.returncode == 0
        stdout_lines = [line.rstrip("\r") for line in result.stdout.split("\n")]
        candidates = [
            backlog_summary(registry, today=day) for day in dict.fromkeys((before, after))
        ]
        _check_hook_matches_rendering(stdout_lines, candidates)
        assert "=== PROCESS HEALTH ===" in stdout_lines


# --------------------------------------------------------------------------- #
# The end-to-end pin's own checker — both branches, no live registry needed
# --------------------------------------------------------------------------- #
class TestHookMatchChecker:
    """Pins ``_check_hook_matches_rendering``, so the end-to-end pin cannot self-disable.

    The empty-rendering branch is otherwise unreachable in this repo (the live registry has
    unclosed gates), which is exactly how a vacuous assertion survives review.
    """

    def test_matching_rendering_passes(self) -> None:
        _check_hook_matches_rendering(["noise", "  [!] A", "  B", "more"], [["  [!] A", "  B"]])

    def test_missing_line_fails(self) -> None:
        with pytest.raises(AssertionError, match="matched no candidate"):
            _check_hook_matches_rendering(["noise", "  [!] A"], [["  [!] A", "  B"]])

    def test_second_candidate_may_match(self) -> None:
        """The midnight-rollover allowance: either date's rendering is acceptable."""
        _check_hook_matches_rendering(["  [!] B"], [["  [!] A"], ["  [!] B"]])

    def test_empty_rendering_is_not_a_free_pass(self) -> None:
        """Nothing owed + hook still nagging must FAIL, not pass vacuously."""
        with pytest.raises(AssertionError, match="still nagged"):
            _check_hook_matches_rendering(["  [!] EDUCATION DEBT: 1 gate"], [[]])

    def test_empty_rendering_with_a_silent_hook_passes(self) -> None:
        _check_hook_matches_rendering(["=== PROCESS HEALTH ===", "  [ok] fine"], [[]])


# --------------------------------------------------------------------------- #
# Governance boundary — this must NOT become a build condition
# --------------------------------------------------------------------------- #
class TestGovernanceBoundary:
    def test_quality_gate_has_no_education_check(self) -> None:
        """governance-mechanisms.md Row 6: making Principle #5 a build condition needs
        its own /plan and a Steward gate. Surfacing it at session start does not."""
        text = QUALITY_GATE.read_text(encoding="utf-8")
        assert "gate_registry" not in text
        assert "gates.yaml" not in text
        assert "backlog_summary" not in text

    def test_settings_still_wires_the_session_start_hook(self) -> None:
        """The nudge is only ever seen if settings.json still runs this hook.

        Deliberately **matcher-agnostic**. It asserts the wiring exists, not which events
        trigger it, so applying the matcher edit reported in ``out_of_scope_needed`` does
        NOT turn this test red -- while unwiring the hook entirely, which is the change
        that would actually silence the backlog, still does. Measured 2026-08-09 the
        matcher was ``resume|compact``; that value is a snapshot, not an assertion.
        """
        settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        entries = settings["hooks"]["SessionStart"]
        assert entries, "SessionStart is not wired at all"
        commands = [hook["command"] for entry in entries for hook in entry["hooks"]]
        assert any("session-start.ps1" in command for command in commands), commands

    def test_settings_matcher_uses_only_recognised_event_tokens(self) -> None:
        """A typo in the matcher silently disables the hook; nothing else would catch it.

        This replaces an earlier assertion that the matcher equalled ``"resume|compact"``
        exactly, which went red on the developer applying the edit this slice asks for.
        Asserting the *token vocabulary* instead keeps the signal (``resume|compakt``
        still fails) while passing under any legitimate matcher, including the widened
        one.

        ``KNOWN_SESSION_START_EVENTS`` is NOT from official harness documentation --
        none is readable from this repo. It is the union of the values used by two
        independent third-party projects vendored under
        ``.claude/worktrees/external-analysis/`` (superpowers ``hooks/hooks.json`` and
        ``docs/windows/polyglot-hooks.md``; claude-flow ``@claude-flow/cli``). Treat it
        as evidence, not as a spec: if the harness gains an event, widen this set.
        """
        settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        for entry in settings["hooks"]["SessionStart"]:
            matcher = entry.get("matcher")
            if matcher is None:  # no matcher == fires on every event; legal
                continue
            unknown = set(matcher.split("|")) - KNOWN_SESSION_START_EVENTS
            assert not unknown, (
                f"unrecognised SessionStart event token(s) {sorted(unknown)} in matcher "
                f"{matcher!r} -- a typo here silently stops the hook from ever running"
            )

    @pytest.mark.parametrize("path", PROSE_FILES, ids=lambda p: p.name)
    def test_prose_points_at_the_live_matcher(self, path: Path) -> None:
        """Every file describing the surfacing carries MATCHER_POINTER.

        Scope, stated exactly: this is a **presence** check on one sentence. It fails when
        that sentence is deleted or reworded. It does NOT detect a false claim added
        alongside it — the pointer being present says nothing about the other sentences in
        the file. That gap is covered by
        ``test_prose_makes_no_unqualified_session_start_claim``; the two are separate
        because a previous revision's docstring claimed this one did both, and a mutation
        (an outright false sentence added next to the pointer) showed it did not.
        """
        assert MATCHER_POINTER in _prose(path.read_text(encoding="utf-8")), (
            f"{path.name} describes the backlog surfacing without pointing at the matcher; "
            f"expected the sentence: {MATCHER_POINTER!r}"
        )

    @pytest.mark.parametrize(
        ("sentence", "is_offence"),
        [
            ("The backlog is surfaced at session start, on every session.", True),
            ("The nudge appears at session start.", True),
            ("It runs on every session.", True),
            ("Every fresh session shows the backlog.", True),
            ("The hook does not run on every session.", False),
            ("Which SessionStart events run it is set by the matcher in settings.json.", False),
            ("It surfaced on resume/compaction but not on a fresh session.", False),
            ("It appears at session start only on the events the matcher selects.", False),
            ("``backlog`` is the rendering consumed by the SessionStart hook.", False),
            ("Nothing here proves the hook ever runs in a real session.", False),
        ],
    )
    def test_session_start_claim_checker_is_itself_correct(
        self, sentence: str, is_offence: bool
    ) -> None:
        """Pins the heuristic, so a broken checker cannot silently pass every file.

        The first case is the exact mutation that a previous revision's prose test failed
        to catch: an outright false claim added while leaving MATCHER_POINTER intact.
        """
        assert bool(_unqualified_session_start_claims(sentence)) is is_offence

    @pytest.mark.parametrize("path", CLAIM_CHECKED_FILES, ids=lambda p: p.name)
    def test_prose_makes_no_unqualified_session_start_claim(self, path: Path) -> None:
        """No mechanism file may claim a surfacing schedule the matcher does not give it.

        The backlog surfaces only on the SessionStart events the matcher selects, so an
        unqualified claim is false — and this slice's whole subject is the difference
        between a comfortable story and a true one. Heuristic, not proof: it checks the
        phrasings in ``_TIMING_CLAIM_TRIGGERS`` and no others, over
        ``CLAIM_CHECKED_FILES`` (which excludes this module — see that constant).
        """
        offenders = _unqualified_session_start_claims(path.read_text(encoding="utf-8"))
        assert offenders == [], (
            f"{path.name} claims when the backlog surfaces without naming the matcher, the "
            f"events it selects, or a limit: {offenders}"
        )

    def test_governance_doc_debt_and_its_acknowledgement_stay_in_sync(self) -> None:
        """The debt this change leaves in a file it may not edit has a queryable home.

        Surfacing the backlog falsifies three sentences in
        ``docs/education/governance-mechanisms.md`` Row 6 ("Nothing **warns** either.",
        "Nothing notices.", and the "weakest class of control ... the only one operating
        here" sentence). That file is out of scope here, so the correction is reported in
        ``out_of_scope_needed`` and acknowledged in ``OWED_DEBT_FILES``.

        A debt recorded only in a comment is exactly the look-if-you-remember control the
        doc indicts, so this asserts the PAIR instead: doc-still-false and
        note-still-present must agree. Correcting the doc turns this red until the notes
        are deleted; deleting the notes while the doc is still false turns it red too. Both
        gone (the debt properly paid) is green.
        """
        doc = GOVERNANCE_DOC.read_text(encoding="utf-8")
        stale = [s for s in GOVERNANCE_DOC_STALE_SENTENCES if s in doc]
        noted = [p for p in OWED_DEBT_FILES if OWED_DEBT_TOKEN in p.read_text(encoding="utf-8")]

        if stale:
            assert len(noted) == len(OWED_DEBT_FILES), (
                f"{GOVERNANCE_DOC.name} still carries {len(stale)} sentence(s) this change "
                f"falsified {stale!r}, but the acknowledgement token {OWED_DEBT_TOKEN!r} is "
                f"missing from {[p.name for p in OWED_DEBT_FILES if p not in noted]}"
            )
        else:
            assert noted == [], (
                f"{GOVERNANCE_DOC.name} has been corrected -- now delete the stale "
                f"{OWED_DEBT_TOKEN!r} note from {[p.name for p in noted]}"
            )

    def test_clearing_a_gate_does_not_destroy_the_registry_header(self, tmp_path: Path) -> None:
        """Following the nudge's own advice must not delete the registry's documentation.

        The nudge names ``clear``. Before ``read_header`` existed, that command took the
        registry header to **zero** lines, deleting the seeding provenance and the CLI
        usage block. Reproduced 2026-08-09 against commit ``31bfe09``, whose header was 16
        lines (``git show 31bfe09:docs/education/gates.yaml | grep -n '^version:'`` ->
        ``17:version: 1``); the full command is in ``read_header``'s docstring. That count
        is a property of that commit, not a constant — this test pins the invariant
        instead, running the real command against a real copy of whatever header the live
        registry currently carries.
        """
        original = LIVE_REGISTRY.read_text(encoding="utf-8")
        header = read_header(LIVE_REGISTRY)
        assert header.count("\n") > 5, "the live registry is expected to carry a real header"
        assert "gate_registry.py backlog" in header

        path = tmp_path / "gates.yaml"
        path.write_text(original, encoding="utf-8")
        gate_id = load_registry(path)["gates"][0]["gate_id"]
        rc = main(
            [
                "--registry",
                str(path),
                "clear",
                "--gate-id",
                gate_id,
                "--session-id",
                "TEST",
                "--discussion-id",
                "TEST",
            ]
        )
        assert rc == 0
        assert path.read_text(encoding="utf-8").startswith(header)
        assert load_registry(path)["gates"][0]["status"] == "cleared"

    def test_gates_yaml_header_documents_the_backlog_command(self) -> None:
        """Pins the cross-file claim: the registry header names a real subcommand."""
        header = LIVE_REGISTRY.read_text(encoding="utf-8")
        assert "gate_registry.py backlog" in header
        # ...and it really is a subcommand, not just prose.
        assert build_parser().parse_args(["backlog"]).command == "backlog"
