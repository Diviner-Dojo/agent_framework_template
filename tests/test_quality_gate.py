"""Tests for scripts/quality_gate.py — the opt-in --notify task-boundary hook.

Covers `_notify_outcome`, the best-effort push-notification hook added so a
developer can be pinged on their phone when a long manual gate run finishes.
The hook must:
  - do nothing unless --notify was passed (so the pre-commit hook stays silent),
  - fire a success ping on pass and a high-priority warning on fail / setup error,
  - never raise — a notification failure must not change the gate's exit code.
"""

import argparse
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts to path for import (mirrors tests/test_notify.py).
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

# All seven gate checks, in the order quality_gate.py runs and counts them.
_ALL_CHECKS = ["format", "lint", "tests", "coverage", "adrs", "reviews", "regression"]


def _make_args(skips: set[str] | None = None) -> argparse.Namespace:
    """Build an args Namespace with the seven ``skip_*`` flags.

    Pass the set of check names to skip (e.g. ``{"tests", "coverage"}``).
    """
    skips = skips or set()
    return argparse.Namespace(**{f"skip_{name}": (name in skips) for name in _ALL_CHECKS})


class TestNotifyOutcome:
    """Tests for the opt-in --notify push-notification hook (_notify_outcome)."""

    @patch("notify.send_notification")
    def test_disabled_is_noop(self, mock_send: MagicMock) -> None:
        """No notification is sent when --notify was not passed."""
        from quality_gate import _notify_outcome

        _notify_outcome(7, 7, enabled=False)
        mock_send.assert_not_called()

    @patch("notify.send_notification")
    def test_pass_fires_success(self, mock_send: MagicMock) -> None:
        """A passing gate sends a success ping at default (non-high) priority."""
        from quality_gate import _notify_outcome

        _notify_outcome(7, 7, enabled=True)

        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        assert kwargs.get("tags") == "white_check_mark"
        # Success path intentionally omits priority (stays at the ntfy default).
        # Assert absence, not just "not high" — the latter passes vacuously.
        assert "priority" not in kwargs

    @patch("notify.send_notification")
    def test_fail_fires_high_priority_warning(self, mock_send: MagicMock) -> None:
        """A failing gate sends a high-priority warning ping reflecting the count."""
        from quality_gate import _notify_outcome

        _notify_outcome(5, 7, enabled=True)

        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        assert kwargs.get("priority") == "high"
        assert kwargs.get("tags") == "warning"
        assert "5/7" in args[0]

    @patch("notify.send_notification")
    def test_setup_error_fires_distinct_ping(self, mock_send: MagicMock) -> None:
        """A pre-check setup failure sends a distinct high-priority ping."""
        from quality_gate import _notify_outcome

        _notify_outcome(0, 0, enabled=True, setup_error=True)

        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        assert kwargs.get("priority") == "high"
        assert kwargs.get("title") == "Quality Gate: setup error"

    @patch("notify.send_notification")
    def test_message_text_carries_no_paths(self, mock_send: MagicMock) -> None:
        """Confidentiality: ntfy.sh is a public relay — message must be generic.

        Asserts the notification text contains no filesystem path separators or
        drive-letter patterns that could leak a private path if intercepted.
        """
        from quality_gate import _notify_outcome

        _notify_outcome(6, 7, enabled=True)

        args, kwargs = mock_send.call_args
        payload = " ".join([str(args[0]), str(kwargs.get("title", ""))])
        assert "/" not in payload.replace("6/7", "")  # only the count ratio uses '/'
        assert "\\" not in payload
        assert ":\\" not in payload

    @patch("notify.send_notification")
    def test_send_failure_never_raises(self, mock_send: MagicMock) -> None:
        """A notification error must never propagate (the never-crash-caller rule)."""
        from quality_gate import _notify_outcome

        mock_send.side_effect = RuntimeError("ntfy exploded")

        # Must not raise even though the underlying send blew up.
        _notify_outcome(7, 7, enabled=True)
        mock_send.assert_called_once()

    def test_notify_module_missing_never_raises(self) -> None:
        """If notify.py is not importable, the helper swallows it and never raises.

        Exercises the load-bearing never-crash path for the most plausible
        production failure: scripts/ not on sys.path. Forcing ``None`` into
        ``sys.modules["notify"]`` makes ``from notify import ...`` raise
        ImportError, which the helper's ``except`` must absorb.
        """
        import sys

        original = sys.modules.get("notify")
        sys.modules["notify"] = None  # type: ignore[assignment]
        try:
            from quality_gate import _notify_outcome

            # Must complete without raising despite the unimportable module.
            _notify_outcome(7, 7, enabled=True)
        finally:
            if original is not None:
                sys.modules["notify"] = original
            else:
                sys.modules.pop("notify", None)


class TestBuildOutcomeRecord:
    """Tests for _build_outcome_record — the honest gate-log record builder.

    Guards the C / gate-log-integrity fix: a run that skipped checks (via
    --skip-*) must never be recorded as a clean, complete ``overall: pass``
    (Principle #2 — capture must be honest).
    """

    def test_all_checks_ran_and_passed_is_clean_pass(self) -> None:
        """Every check ran and passed → overall 'pass', no skips."""
        from quality_gate import _build_outcome_record

        record = _build_outcome_record(_make_args(), [True] * 7, passed=7, total=7)

        assert record["overall"] == "pass"
        assert record["skipped_count"] == 0
        assert record["passed_count"] == 7
        assert record["total"] == 7
        assert set(record["checks"].values()) == {"pass"}

    @pytest.mark.regression
    def test_skipped_checks_are_not_a_clean_pass(self) -> None:
        """Regression (C / gate-log integrity): skipping checks must NOT log 'pass'.

        Old code logged ``overall: "pass"`` whenever ``passed == total``, but
        ``total`` excluded skipped checks — so a run that skipped tests and
        coverage and passed the other five was recorded as a clean pass. The
        fix records 'pass_with_skips' and a skipped_count instead.
        """
        from quality_gate import _build_outcome_record

        # tests + coverage skipped; remaining 5 ran and passed → total counts 5.
        record = _build_outcome_record(
            _make_args({"tests", "coverage"}), [True] * 5, passed=5, total=5
        )

        assert record["overall"] == "pass_with_skips"
        assert record["skipped_count"] == 2
        assert record["checks"]["tests"] == "skipped"
        assert record["checks"]["coverage"] == "skipped"
        assert record["checks"]["format"] == "pass"
        # Spot-check checks *after* the skipped pair to confirm post-skip index
        # alignment — a misaligned idx walk would misread these, not 'format'.
        assert record["checks"]["adrs"] == "pass"
        assert record["checks"]["regression"] == "pass"

    def test_vacuous_all_skipped_is_not_a_clean_pass(self) -> None:
        """All checks skipped (total == 0) verifies nothing → 'pass_with_skips'."""
        from quality_gate import _build_outcome_record

        record = _build_outcome_record(_make_args(set(_ALL_CHECKS)), [], passed=0, total=0)

        assert record["overall"] == "pass_with_skips"
        assert record["skipped_count"] == 7
        assert set(record["checks"].values()) == {"skipped"}

    def test_a_failed_check_overrides_skips(self) -> None:
        """A check that ran and failed → overall 'fail', even with skips present."""
        from quality_gate import _build_outcome_record

        # coverage skipped; tests failed among the six that ran.
        results = [True, True, False, True, True, True]  # tests (idx 2) failed
        record = _build_outcome_record(_make_args({"coverage"}), results, passed=5, total=6)

        assert record["overall"] == "fail"
        assert record["checks"]["tests"] == "fail"
        assert record["checks"]["coverage"] == "skipped"
        assert record["skipped_count"] == 1

    def test_last_check_skipped_preserves_index_alignment(self) -> None:
        """Skipping the LAST check (regression, idx 6) keeps the idx walk aligned.

        Every other skip test skips a middle check; this is the only case that
        exercises the ``idx < len(results)`` bound at the final position, where
        an off-by-one in the walk would surface.
        """
        from quality_gate import _build_outcome_record

        # regression skipped; the other six ran and passed → total counts 6.
        record = _build_outcome_record(_make_args({"regression"}), [True] * 6, passed=6, total=6)

        assert record["overall"] == "pass_with_skips"
        assert record["skipped_count"] == 1
        assert record["checks"]["regression"] == "skipped"
        # Every non-skipped check (incl. the now-last 'reviews', idx 5) reads pass.
        assert record["checks"]["reviews"] == "pass"
        assert {k: v for k, v in record["checks"].items() if v != "skipped"} == {
            "format": "pass",
            "lint": "pass",
            "tests": "pass",
            "coverage": "pass",
            "adrs": "pass",
            "reviews": "pass",
        }

    def test_multiple_failures_with_a_skip_is_fail(self) -> None:
        """Two non-adjacent ran-checks fail while one check is skipped → 'fail'."""
        from quality_gate import _build_outcome_record

        # coverage skipped; among the six that ran, lint (idx 1) and reviews
        # (idx 4) fail. results order: format, lint, tests, adrs, reviews, regression.
        results = [True, False, True, True, False, True]
        record = _build_outcome_record(_make_args({"coverage"}), results, passed=4, total=6)

        assert record["overall"] == "fail"
        assert record["checks"]["lint"] == "fail"
        assert record["checks"]["reviews"] == "fail"
        assert record["checks"]["format"] == "pass"
        assert record["checks"]["coverage"] == "skipped"
        assert record["skipped_count"] == 1

    # Every field that existed before SPEC-20260716-233400 — the telemetry
    # consumers' contract. Removing or renaming any of these is a breaking
    # change to the gate-log schema (AC9: additive only).
    _PRE_EXISTING_RECORD_KEYS = {
        "timestamp",
        "overall",
        "passed_count",
        "total",
        "skipped_count",
        "checks",
    }
    _SPEC_233400_ADDITIVE_KEYS = {"profile", "baseline_debt_count", "rebaseline", "fast"}

    @pytest.mark.regression
    def test_record_has_stable_schema_keys(self) -> None:
        """AC9 schema pin: every pre-existing key survives; new keys are additive only.

        Guards the telemetry-consumer contract (_build_outcome_record feeds
        metrics/quality_gate_log.jsonl, read by the Layer B dashboard): the
        SPEC-20260716-233400 fields may extend the record but must never
        rename or remove a pre-existing field.
        """
        from quality_gate import _build_outcome_record

        record = _build_outcome_record(_make_args(), [True] * 7, passed=7, total=7)

        missing = self._PRE_EXISTING_RECORD_KEYS - set(record)
        assert not missing, f"pre-existing gate-log fields removed: {missing}"
        assert set(record) == self._PRE_EXISTING_RECORD_KEYS | self._SPEC_233400_ADDITIVE_KEYS

    def test_new_fields_have_backward_compatible_defaults(self) -> None:
        """AC9: a legacy-style call (no profile/baseline kwargs) yields sane defaults."""
        from quality_gate import _build_outcome_record

        record = _build_outcome_record(_make_args(), [True] * 7, passed=7, total=7)

        assert record["profile"] == "python-fastapi"
        assert record["baseline_debt_count"] == 0
        assert record["rebaseline"] is False
        assert record["fast"] is False

    def test_disabled_checks_do_not_demote_overall(self) -> None:
        """Profile-disabled checks record 'disabled' and keep a clean 'pass'.

        Disabled-by-profile is by-design (markdown-corpus disables all four
        stack checks) — unlike a --skip-* bypass it must NOT read as
        'pass_with_skips', or every corpus repo would never see a clean pass.
        """
        from quality_gate import _build_outcome_record

        record = _build_outcome_record(
            _make_args(),
            [True] * 3,  # adrs, reviews, regression ran and passed
            passed=3,
            total=3,
            profile="markdown-corpus",
            disabled={"format", "lint", "tests", "coverage"},
        )

        assert record["overall"] == "pass"
        assert record["skipped_count"] == 0
        assert record["checks"]["format"] == "disabled"
        assert record["checks"]["coverage"] == "disabled"
        assert record["checks"]["adrs"] == "pass"
        assert record["profile"] == "markdown-corpus"


class TestFormatSummary:
    """Tests for _format_summary — the end-of-run console summary line."""

    @pytest.mark.regression
    @pytest.mark.parametrize(
        "passed,total,skipped",
        [
            (7, 7, 0),  # clean pass
            (6, 6, 1),  # pass_with_skips (the path that had the em-dash)
            (4, 4, 3),  # multiple skips
            (5, 7, 0),  # fail
        ],
    )
    def test_summary_is_ascii_encodable(self, passed: int, total: int, skipped: int) -> None:
        """Regression: the summary must be cp1252-encodable on Windows terminals.

        A non-ASCII char (e.g. an em-dash) in this print path raises
        UnicodeEncodeError on a raw Windows terminal (cp1252) — the same class
        as the context_sensor statusLine and notify-title crashes. Guards the
        skip path specifically, where the original "— not a complete pass" text
        introduced an em-dash.
        """
        from quality_gate import _format_summary

        summary = _format_summary(passed, total, skipped)
        # Must round-trip through cp1252 (the Windows console codec) unchanged.
        summary.encode("cp1252")
        summary.encode("ascii")

    def test_skip_summary_signals_incomplete(self) -> None:
        """A pass with skips is labelled as not-a-complete-pass, not a clean pass."""
        from quality_gate import _format_summary

        assert "not a complete pass" in _format_summary(6, 6, 1)
        assert "skipped" in _format_summary(6, 6, 1)
        assert "not a complete pass" not in _format_summary(7, 7, 0)


# ---------------------------------------------------------------------------
# AC8 — check_promotion_backlog advisory (ADR-0022, R3.2)
# ---------------------------------------------------------------------------


class TestCheckPromotionBacklog:
    """check_promotion_backlog is advisory: always returns True, warns on count trigger,
    is silent on a fresh/empty DB, and its return value is NOT appended to results."""

    def _make_db(self, tmp_path: Path) -> Path:
        """Create a minimal evaluation.db with promotion_candidates + reflections tables."""
        import sqlite3

        (tmp_path / "metrics").mkdir(exist_ok=True)
        db_path = tmp_path / "metrics" / "evaluation.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS promotion_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                finding_pattern TEXT NOT NULL,
                category TEXT NOT NULL,
                sighting_count INTEGER NOT NULL DEFAULT 1,
                first_seen DATETIME NOT NULL,
                last_seen DATETIME NOT NULL,
                promoted BOOLEAN NOT NULL DEFAULT 0,
                promoted_at DATETIME,
                promoted_to TEXT,
                evidence_ids TEXT NOT NULL DEFAULT '[]'
            );
            CREATE TABLE IF NOT EXISTS reflections (
                reflection_id TEXT PRIMARY KEY,
                discussion_id TEXT NOT NULL,
                agent TEXT NOT NULL,
                missed_signal TEXT,
                improvement_rule TEXT,
                confidence_delta REAL,
                promoted BOOLEAN NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL
            );
        """)
        conn.commit()
        conn.close()
        return db_path

    def _insert_candidates(self, db_path: Path, count: int, promoted: bool = False) -> None:
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        for i in range(count):
            conn.execute(
                "INSERT INTO promotion_candidates "
                "(finding_pattern, category, sighting_count, first_seen, last_seen, promoted) "
                "VALUES (?, 'testing', 1, '2026-06-01T00:00:00', '2026-06-01T00:00:00', ?)",
                (f"hash{i:04}", 1 if promoted else 0),
            )
        conn.commit()
        conn.close()

    def test_always_returns_true(self, tmp_path: Path) -> None:
        """AC8: check_promotion_backlog always returns True (advisory, never blocks)."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from unittest.mock import patch

        db_path = self._make_db(tmp_path)
        self._insert_candidates(db_path, 10)  # Over threshold
        with patch("quality_gate.PROJECT_ROOT", tmp_path):
            # Patch DB_PATH inside the function via PROJECT_ROOT
            from quality_gate import check_promotion_backlog

            # Patch the db_path reference inside the function
            with patch("quality_gate.PROJECT_ROOT", tmp_path):
                result = check_promotion_backlog()
        assert result is True

    def test_warns_when_pending_exceeds_threshold(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """AC8: warns when pending candidates > _PROMOTION_BACKLOG_THRESHOLD (5)."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from unittest.mock import patch

        db_path = self._make_db(tmp_path)
        self._insert_candidates(db_path, 6)  # 6 > threshold of 5
        with patch("quality_gate.PROJECT_ROOT", tmp_path):
            from quality_gate import check_promotion_backlog

            check_promotion_backlog()
        captured = capsys.readouterr()
        assert "backlog" in captured.out.lower() or "promotion" in captured.out.lower()

    def test_silent_on_empty_db(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """AC8: no warning when DB is empty (fresh repo)."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from unittest.mock import patch

        self._make_db(tmp_path)  # Empty tables — DB path matters, not the return value
        with patch("quality_gate.PROJECT_ROOT", tmp_path):
            from quality_gate import check_promotion_backlog

            result = check_promotion_backlog()
        assert result is True

    def test_gate_exit_code_zero_when_backlog_warned(self, tmp_path: Path) -> None:
        """AC8: gate exit code is 0 even when promotion backlog warning fires."""
        from unittest.mock import patch

        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

        db_path = self._make_db(tmp_path)
        self._insert_candidates(db_path, 6)
        with patch("quality_gate.PROJECT_ROOT", tmp_path):
            from quality_gate import check_promotion_backlog

            result = check_promotion_backlog()
        # Gate always returns True — caller never receives False to flip exit code.
        assert result is True

    def test_staleness_warn_with_stale_reflection(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Staleness trigger: 1 pending candidate + stale reflection warns without crashing.

        Regression guard for the naive-datetime TypeError (HIGH finding, ADR-0022):
        fromisoformat on a timezone-aware string must not crash when subtracted from
        datetime.now(UTC). Uses a past date well beyond _PROMOTION_STALE_DAYS (30).
        """
        import sqlite3
        from unittest.mock import patch

        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

        db_path = self._make_db(tmp_path)
        # 1 pending candidate (below count-threshold of 5) with a stale last_seen.
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO promotion_candidates "
            "(finding_pattern, category, sighting_count, first_seen, last_seen, promoted) "
            "VALUES ('hash_stale', 'testing', 1, '2025-01-01T00:00:00+00:00', "
            "'2025-01-01T00:00:00+00:00', 0)"
        )
        # Stale reflection — timezone-aware ISO string.
        conn.execute(
            "INSERT INTO reflections "
            "(reflection_id, discussion_id, agent, created_at) "
            "VALUES ('REFL-stale', 'DISC-stale', 'qa-specialist', '2025-01-01T00:00:00+00:00')"
        )
        conn.commit()
        conn.close()

        with patch("quality_gate.PROJECT_ROOT", tmp_path):
            from quality_gate import check_promotion_backlog

            result = check_promotion_backlog()

        assert result is True  # Advisory — never blocks
        captured = capsys.readouterr()
        # Staleness warning fires (>30 days ago).
        assert "backlog" in captured.out.lower() or "promote" in captured.out.lower()

    @pytest.mark.regression
    def test_staleness_with_naive_datetime_does_not_crash(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """qa HIGH fold (DISC-20260612-144008): the actual TypeError repro.

        Rows inserted with bare ISO strings (no timezone offset) made
        fromisoformat return a naive datetime; subtracting it from
        datetime.now(UTC) raised 'TypeError: can't subtract offset-naive and
        offset-aware datetimes' and crashed the advisory check. The fix
        normalizes naive values to UTC. The aware-string sibling test above
        cannot catch this — only a naive string exercises the branch.
        """
        import sqlite3
        from unittest.mock import patch

        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

        db_path = self._make_db(tmp_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO promotion_candidates "
            "(finding_pattern, category, sighting_count, first_seen, last_seen, promoted) "
            "VALUES ('hash_naive', 'testing', 1, '2025-01-01T00:00:00', "
            "'2025-01-01T00:00:00', 0)"
        )
        # Stale reflection with a NAIVE ISO string — the crash trigger.
        conn.execute(
            "INSERT INTO reflections "
            "(reflection_id, discussion_id, agent, created_at) "
            "VALUES ('REFL-naive', 'DISC-naive', 'qa-specialist', '2025-01-01T00:00:00')"
        )
        conn.commit()
        conn.close()

        with patch("quality_gate.PROJECT_ROOT", tmp_path):
            from quality_gate import check_promotion_backlog

            result = check_promotion_backlog()  # Must not raise

        assert result is True
        captured = capsys.readouterr()
        assert "promote" in captured.out.lower() or "backlog" in captured.out.lower()

    def test_promotion_backlog_not_wired_into_results_list(self) -> None:
        """qa LOW fold (DISC-20260612-144008): AC8 source pin.

        check_promotion_backlog is advisory — main() must call it standalone,
        never results.append(...) it (which would let it flip the gate verdict).
        """
        source = (Path(__file__).parent.parent / "scripts" / "quality_gate.py").read_text(
            encoding="utf-8"
        )
        assert "check_promotion_backlog()" in source
        assert "results.append(check_promotion_backlog" not in source


# ---------------------------------------------------------------------------
# check_coverage — scripts/education isolated 80% floor (ADR-0029 §5, qa Q2)
# ---------------------------------------------------------------------------


class TestCheckCoverageIsolatedFloor:
    """The education-tooling coverage floor must be enforced in ISOLATION.

    The aggregate --cov-fail-under is dominated by src/'s statement count, so a
    regression confined to scripts/education/ could hide inside a green TOTAL.
    check_coverage therefore runs a second, isolated `coverage report
    --include=scripts/education/* --fail-under=80` and must fail the check when
    that report fails — including the zero-match "No data" case, which would
    otherwise be silent false assurance.
    """

    @staticmethod
    def _fake_run(pytest_rc: int, coverage_rc: int, coverage_out: str = ""):
        """Build a _run stand-in dispatching on which command is being invoked."""
        import subprocess

        def _run(cmd, cwd=None):  # noqa: ANN001 — mirrors quality_gate._run
            if "pytest" in cmd:
                return subprocess.CompletedProcess(cmd, pytest_rc, stdout="", stderr="")
            assert "coverage" in cmd, f"unexpected command: {cmd}"
            assert "--include=scripts/education/*" in cmd
            assert "--fail-under=80" in cmd
            return subprocess.CompletedProcess(cmd, coverage_rc, stdout=coverage_out, stderr="")

        return _run

    def test_aggregate_pass_isolated_fail_returns_false(self) -> None:
        """[qa Q2] aggregate green + isolated education floor failing -> False."""
        from quality_gate import check_coverage

        fake = self._fake_run(pytest_rc=0, coverage_rc=2, coverage_out="TOTAL   338   170   55%")
        with patch("quality_gate._run", side_effect=fake):
            assert check_coverage() is False

    def test_both_pass_returns_true(self) -> None:
        """Aggregate green + isolated floor green -> True."""
        from quality_gate import check_coverage

        fake = self._fake_run(pytest_rc=0, coverage_rc=0, coverage_out="TOTAL   338   10   97%")
        with patch("quality_gate._run", side_effect=fake):
            assert check_coverage() is True

    def test_zero_match_no_data_returns_false(self) -> None:
        """A zero-match include ('No data to report.', exit 1) must FAIL the check."""
        from quality_gate import check_coverage

        fake = self._fake_run(pytest_rc=0, coverage_rc=1, coverage_out="No data to report.")
        with patch("quality_gate._run", side_effect=fake):
            assert check_coverage() is False

    def test_include_glob_matches_the_real_education_files(self) -> None:
        """Guard against silent zero-match: the include glob must actually match
        the two load-bearing education modules on disk."""
        import fnmatch

        project_root = Path(__file__).parent.parent
        edu_files = [
            str(p.relative_to(project_root)).replace("\\", "/")
            for p in (project_root / "scripts" / "education").glob("*.py")
        ]
        matched = [f for f in edu_files if fnmatch.fnmatch(f, "scripts/education/*")]
        names = {Path(f).name for f in matched}
        assert "gate_registry.py" in names
        assert "ingest_walkthrough_session.py" in names


# ---------------------------------------------------------------------------
# SPEC-20260716-233400 — green-able gate + stack profiles + ergonomics riders
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent
_GOLDEN_FIXTURE = Path(__file__).parent / "fixtures" / "gate_summary_golden.txt"
_PRE_COMMIT_HOOK = _REPO_ROOT / ".claude" / "hooks" / "pre-commit-gate.sh"


def _completed(cmd: list, rc: int = 0, stdout: str = "", stderr: str = ""):
    """Build a CompletedProcess for the _run() seam fakes."""
    import subprocess

    return subprocess.CompletedProcess(cmd, rc, stdout=stdout, stderr=stderr)


def _fake_run_factory(rules: list | None = None, record: list | None = None):
    """Fake for the single ``_run()`` seam (qa 6 — the one mock target).

    ``rules`` is a list of ``(substrings, rc, stdout)``; the first rule whose
    substrings all appear in the joined command wins. Default: rc 0, empty out.
    """

    def fake(cmd, cwd=None):  # noqa: ANN001 — mirrors quality_gate._run
        if record is not None:
            record.append([str(c) for c in cmd])
        joined = " ".join(str(c) for c in cmd)
        for match, rc, out in rules or []:
            if all(m in joined for m in match):
                return _completed(cmd, rc, out)
        return _completed(cmd, 0, "")

    return fake


def _gate_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    profiles: str | None = None,
    baseline: str | None = None,
    marker: str | None = "pyproject.toml",
):
    """Point the gate's config/log/detection roots at tmp_path.

    Integrity-check globals (ADR_DIR, REVIEWS_DIR, REGRESSION_LEDGER, SRC_DIR,
    TESTS_DIR) stay on the real repo, which is green. Setting PROJECT_ROOT to
    tmp_path also makes _get_staged_code_files return [] (tmp is not a git
    repo — fails safe), so review-existence is deterministic regardless of
    what is actually staged while the suite runs.
    """
    import quality_gate as qg

    monkeypatch.setattr(qg, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(qg, "QUALITY_GATE_LOG", tmp_path / "metrics" / "gate_log.jsonl")
    monkeypatch.setattr(qg, "GATE_PROFILES_FILE", tmp_path / "gate_profiles.yaml")
    monkeypatch.setattr(qg, "GATE_BASELINE_FILE", tmp_path / "gate_baseline.json")
    # check_regression_ledger resolves ledger test paths against PROJECT_ROOT
    # (now tmp), so the REAL ledger's guards would all read as missing. Give
    # tmp a self-consistent one-entry ledger instead.
    ledger = tmp_path / "regression-ledger.md"
    ledger.write_text(
        "| File | Bug Description | Root Cause Class | Fix Date | Test File "
        "| Test Function |\n"
        "|------|---|---|---|---|---|\n"
        "| src/app.py | d | Missing Null | 2026-01-01 | tests/test_app.py | test_ok |\n",
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir(exist_ok=True)
    (tmp_path / "tests" / "test_app.py").write_text("def test_ok():\n    pass\n", encoding="utf-8")
    monkeypatch.setattr(qg, "REGRESSION_LEDGER", ledger)
    # ADR_DIR is an import-time constant, so without repointing it these
    # integration tests would silently depend on the REAL docs/adr/ staying
    # green (qa review, 2026-07-17). One trivially-valid stub ADR keeps the
    # golden summary shape ("N ADR(s)") intact.
    adr_dir = tmp_path / "adr"
    adr_dir.mkdir(exist_ok=True)
    (adr_dir / "ADR-0001-stub.md").write_text(
        "---\n"
        "adr_id: ADR-0001\n"
        "title: Stub\n"
        "status: accepted\n"
        "date: 2026-01-01\n"
        "decision_makers: [dev]\n"
        "discussion_id: DISC-00000000-000000-stub\n"
        "---\n\n"
        "## Context\nx\n\n## Decision\nx\n\n## Alternatives Considered\nx\n\n"
        "## Consequences\nx\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(qg, "ADR_DIR", adr_dir)
    if marker:
        (tmp_path / marker).write_text("", encoding="utf-8")
    if profiles is not None:
        (tmp_path / "gate_profiles.yaml").write_text(profiles, encoding="utf-8")
    if baseline is not None:
        (tmp_path / "gate_baseline.json").write_text(baseline, encoding="utf-8")
    return qg


def _run_gate(qg, monkeypatch: pytest.MonkeyPatch, argv: list[str], fake_run) -> int:
    """Invoke main() with a fake _run seam and the given CLI args."""
    monkeypatch.setattr(qg, "_run", fake_run)
    monkeypatch.setattr(sys, "argv", ["quality_gate.py", *argv])
    return qg.main()


def _read_log(tmp_path: Path) -> dict:
    """Read the last JSONL record the gate wrote in this env."""
    import json

    lines = (tmp_path / "metrics" / "gate_log.jsonl").read_text(encoding="utf-8").splitlines()
    return json.loads(lines[-1])


def _baseline_json(fps: list[tuple[str, str, str]]) -> str:
    """Serialize fingerprints into a valid gate_baseline.json payload."""
    import json

    return json.dumps(
        {
            "schema_version": 1,
            "fingerprints": [{"check": c, "file": f, "code": code} for c, f, code in fps],
        }
    )


def _ruff_json(entries: list[tuple[str, str]]) -> str:
    """Serialize (filename, code) pairs into ruff check --output-format=json shape."""
    import json

    return json.dumps([{"filename": f, "code": c} for f, c in entries])


def _normalize_gate_stdout(text: str) -> list[str]:
    """Normalize gate stdout for the AC6 golden comparison.

    Strips ANSI + CR, drops blank/advisory (WARN/NOTICE) lines — those are
    timing- and state-dependent — and masks digit runs, so the comparison pins
    the load-bearing structure: check labels, order, PASS statuses, and the
    final summary shape.
    """
    import re

    ansi = re.compile(r"\x1b\[[0-9;]*m")
    out: list[str] = []
    for raw in text.replace("\r", "").split("\n"):
        line = ansi.sub("", raw).rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("WARN", "NOTICE")):
            continue
        out.append(re.sub(r"\d+", "N", line))
    return out


class TestProfileConfigLoading:
    """_load_profiles_config — fail closed on anything malformed (R2.3, qa 5)."""

    def test_absent_file_returns_empty_config(self, tmp_path: Path) -> None:
        from quality_gate import _load_profiles_config

        assert _load_profiles_config(tmp_path / "nope.yaml") == {}

    @pytest.mark.parametrize(
        "content",
        [
            "{",  # malformed YAML
            "",  # empty file (qa 5)
            "- a\n- b",  # top level not a mapping
            "profiles: {}",  # missing schema_version
            "schema_version: 2\nprofiles: {}",  # unknown schema version
            "schema_version: 1\nprofiles: [a]",  # profiles not a mapping
            "schema_version: 1\nprofiles:\n  p1: [x]",  # profile entry not a mapping
            "schema_version: 1\nprofiles:\n  p1:\n    checks: [x]",  # checks not a mapping
            "schema_version: 1\nprofiles:\n  p1:\n    checks:\n      lint: yes",
            "schema_version: 1\nprofiles:\n  p1:\n    checks:\n      lint: {command: ruff}",
            "schema_version: 1\nprofile: [not-a-string]\nprofiles: {}",
        ],
    )
    def test_malformed_config_fails_closed(self, tmp_path: Path, content: str) -> None:
        from quality_gate import GateConfigError, _load_profiles_config

        path = tmp_path / "gate_profiles.yaml"
        path.write_text(content, encoding="utf-8")
        with pytest.raises(GateConfigError):
            _load_profiles_config(path)

    @pytest.mark.regression
    @pytest.mark.parametrize("value", ['"abc"', "true", "-5", "[80]"])
    def test_malformed_fail_under_fails_closed(self, tmp_path: Path, value: str) -> None:
        """Security review (2026-07-17): an unvalidated fail_under would reach
        int() at dispatch and raise a traceback instead of the one-line ERROR."""
        from quality_gate import GateConfigError, _load_profiles_config

        path = tmp_path / "gate_profiles.yaml"
        path.write_text(
            "schema_version: 1\nprofiles:\n  p1:\n    checks:\n"
            f"      coverage: {{enabled: true, fail_under: {value}}}",
            encoding="utf-8",
        )
        with pytest.raises(GateConfigError):
            _load_profiles_config(path)

    @pytest.mark.regression
    def test_empty_command_list_fails_closed(self, tmp_path: Path) -> None:
        """qa checkpoint (2026-07-17): command: [] passed validation but was
        falsy at dispatch, silently falling through to the built-in check."""
        from quality_gate import GateConfigError, _load_profiles_config

        path = tmp_path / "gate_profiles.yaml"
        path.write_text(
            "schema_version: 1\nprofiles:\n  p1:\n    checks:\n      lint: {command: []}",
            encoding="utf-8",
        )
        with pytest.raises(GateConfigError):
            _load_profiles_config(path)

    def test_minimal_valid_config_falls_back_to_builtins(self, tmp_path: Path) -> None:
        from quality_gate import _BUILTIN_PROFILES, _load_profiles_config, _merged_profiles

        path = tmp_path / "gate_profiles.yaml"
        path.write_text("schema_version: 1\n", encoding="utf-8")
        config = _load_profiles_config(path)
        assert _merged_profiles(config) == _BUILTIN_PROFILES

    def test_integrity_check_key_is_ignored_with_warning(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """R2.4/F4: a checks key naming an integrity check has NO effect —
        warned and ignored, never honored, never a crash."""
        from quality_gate import _load_profiles_config

        path = tmp_path / "gate_profiles.yaml"
        path.write_text(
            "schema_version: 1\n"
            "profiles:\n"
            "  p1:\n"
            "    checks:\n"
            "      reviews: {enabled: false}\n"
            "      lint: {enabled: true}\n",
            encoding="utf-8",
        )
        config = _load_profiles_config(path)
        err = capsys.readouterr().err
        assert "ignoring unknown check key 'reviews'" in err
        # The key survives in the raw dict but the dispatch layer only ever
        # reads _STACK_CHECKS keys — asserted end-to-end in TestMainProfileRuns.
        assert "p1" in config["profiles"]


class TestProfileResolution:
    """_resolve_profile — precedence flag > pin > auto-detect (R2.2 / AC4)."""

    def test_flag_beats_config_pin(self, tmp_path: Path) -> None:
        from quality_gate import _resolve_profile

        name, _ = _resolve_profile("flutter-dart", {"profile": "markdown-corpus"}, root=tmp_path)
        assert name == "flutter-dart"

    def test_config_pin_beats_autodetect(self, tmp_path: Path) -> None:
        from quality_gate import _resolve_profile

        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        name, _ = _resolve_profile(None, {"profile": "markdown-corpus"}, root=tmp_path)
        assert name == "markdown-corpus"

    def test_autodetect_pubspec_beats_pyproject(self, tmp_path: Path) -> None:
        from quality_gate import _autodetect_profile

        (tmp_path / "pubspec.yaml").write_text("", encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        assert _autodetect_profile(tmp_path)[0] == "flutter-dart"

    def test_autodetect_pyproject_then_corpus_fallback(self, tmp_path: Path) -> None:
        from quality_gate import _autodetect_profile

        assert _autodetect_profile(tmp_path)[0] == "markdown-corpus"
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        assert _autodetect_profile(tmp_path)[0] == "python-fastapi"

    @pytest.mark.parametrize("via", ["flag", "pin"])
    def test_unknown_profile_fails_closed(self, tmp_path: Path, via: str) -> None:
        from quality_gate import GateConfigError, _resolve_profile

        with pytest.raises(GateConfigError):
            if via == "flag":
                _resolve_profile("bogus", {}, root=tmp_path)
            else:
                _resolve_profile(None, {"profile": "bogus"}, root=tmp_path)

    def test_resolution_notice_goes_to_stderr_not_stdout(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """R2.5/AC6: the notice must not pollute the golden stdout summary."""
        from quality_gate import _resolve_profile

        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        _resolve_profile(None, {}, root=tmp_path)
        captured = capsys.readouterr()
        assert "profile: python-fastapi (auto-detected: pyproject.toml)" in captured.err
        assert "auto-detected" not in captured.out

    def test_dual_marker_monorepo_warns_loudly(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Independent-perspective review (2026-07-17): both pubspec.yaml and
        pyproject.toml present must not silently disable python code checks —
        same failure mode as F6, on the sibling auto-detect branch."""
        from quality_gate import _resolve_profile

        (tmp_path / "pubspec.yaml").write_text("", encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        name, _ = _resolve_profile(None, {}, root=tmp_path)
        captured = capsys.readouterr()
        assert name == "flutter-dart"
        assert "both pubspec.yaml and pyproject.toml present" in captured.err
        assert "WARN" in captured.out

    def test_markdown_corpus_with_py_files_warns_loudly(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """F6: deleting pyproject.toml must not silently disable code checks."""
        from quality_gate import _resolve_profile

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
        name, _ = _resolve_profile(None, {}, root=tmp_path)
        captured = capsys.readouterr()
        assert name == "markdown-corpus"
        assert "code checks are disabled" in captured.err
        assert "WARN" in captured.out  # loud on the human channel too


class TestCommandAllowList:
    """_command_allowed — argv[0] allow-list, bare names only (F3)."""

    @pytest.mark.parametrize(
        "argv0", ["ruff", "pytest", "coverage", "python", "dart", "flutter", "PYTHON", "ruff.exe"]
    )
    def test_bare_allow_listed_names_pass(self, argv0: str) -> None:
        from quality_gate import _command_allowed

        assert _command_allowed([argv0, "--version"]) is True

    @pytest.mark.parametrize("argv0", ["bash", "rm", "git", "npm", "powershell"])
    def test_non_allow_listed_names_fail(self, argv0: str) -> None:
        from quality_gate import _command_allowed

        assert _command_allowed([argv0]) is False

    @pytest.mark.regression
    @pytest.mark.parametrize(
        "argv0",
        [
            "C:/attacker/python.exe",
            "C:\\attacker\\python.exe",
            "./python",
            "../python",
            "scripts/python",
            "c:python",
        ],
    )
    def test_path_bearing_argv0_is_rejected(self, argv0: str) -> None:
        """Security checkpoint (2026-07-17): a path-bearing argv[0] whose
        BASENAME is allow-listed must still be rejected — subprocess would
        execute the attacker-controlled path verbatim."""
        from quality_gate import _command_allowed

        assert _command_allowed([argv0, "-c", "1"]) is False

    def test_empty_command_is_rejected(self) -> None:
        from quality_gate import _command_allowed

        assert _command_allowed([]) is False

    def test_disallowed_command_fails_the_check_with_error_line(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        from quality_gate import check_profile_command

        assert check_profile_command("format", ["bash", "-c", "true"]) is False
        captured = capsys.readouterr()
        assert "ERROR format: " in captured.err
        assert "allow-list" in captured.err

    def test_allowed_command_runs_via_seam_and_truncates_output(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """R3.4: failing tool output is truncated to the last 20 lines."""
        from quality_gate import check_profile_command

        big_output = "\n".join(f"line{i}" for i in range(30))
        fake = _fake_run_factory(rules=[(("dart",), 1, big_output)])
        with patch("quality_gate._run", side_effect=fake):
            assert check_profile_command("lint", ["dart", "analyze"]) is False
        captured = capsys.readouterr()
        assert "line29" in captured.out
        assert "line5" not in captured.out
        assert "truncated" in captured.out
        assert "rerun for full output" in captured.out
        assert "ERROR lint: " in captured.err

    def test_allowed_command_passing(self) -> None:
        from quality_gate import check_profile_command

        fake = _fake_run_factory()
        with patch("quality_gate._run", side_effect=fake):
            assert check_profile_command("tests", ["flutter", "test"]) is True


class TestBaselineFile:
    """_load_baseline / _write_baseline — corrupt fails closed (R1.1a / AC3a)."""

    def test_absent_baseline_is_empty(self, tmp_path: Path) -> None:
        from quality_gate import _load_baseline

        assert _load_baseline(tmp_path / "nope.json") == set()

    def test_roundtrip_write_then_load(self, tmp_path: Path) -> None:
        from quality_gate import _load_baseline, _write_baseline

        fps = {("lint", "src/a.py", "F401"), ("format", "src/b.py", "reformat")}
        path = tmp_path / "gate_baseline.json"
        _write_baseline(fps, path)
        assert _load_baseline(path) == fps

    def test_write_is_deterministically_sorted(self, tmp_path: Path) -> None:
        """Stable bytes → reviewable diffs (fingerprints reviewed as diffs)."""
        from quality_gate import _write_baseline

        a, b = tmp_path / "a.json", tmp_path / "b.json"
        _write_baseline({("lint", "z.py", "F401"), ("lint", "a.py", "E501")}, a)
        _write_baseline({("lint", "a.py", "E501"), ("lint", "z.py", "F401")}, b)
        assert a.read_bytes() == b.read_bytes()

    @pytest.mark.parametrize(
        "content",
        [
            "not json at all",
            "",  # 0-byte (AC3a)
            "[]",  # non-dict
            '{"schema_version": 99, "fingerprints": []}',
            '{"schema_version": 1}',  # missing fingerprints
            '{"schema_version": 1, "fingerprints": {}}',  # not a list
            '{"schema_version": 1, "fingerprints": [{"check": "lint"}]}',  # missing keys
            '{"schema_version": 1, "fingerprints": '
            '[{"check": "tests", "file": "x", "code": "y"}]}',
        ],
    )
    def test_corrupt_baseline_fails_closed(self, tmp_path: Path, content: str) -> None:
        """AC3a: existing-but-invalid is NEVER silently treated as empty."""
        from quality_gate import GateConfigError, _load_baseline

        path = tmp_path / "gate_baseline.json"
        path.write_text(content, encoding="utf-8")
        with pytest.raises(GateConfigError):
            _load_baseline(path)


class TestFingerprintCollectors:
    """Fingerprints come from structured tool output only (qa 3 / qa 4)."""

    def test_format_collector_normalizes_to_posix(self) -> None:
        from quality_gate import _collect_format_fingerprints

        fake = _fake_run_factory(
            rules=[(("format", "--check"), 1, "Would reformat: src\\pkg\\mod.py\nDone.")]
        )
        with patch("quality_gate._run", side_effect=fake):
            fps = _collect_format_fingerprints()
        assert fps == {("format", "src/pkg/mod.py", "reformat")}

    def test_lint_collector_parses_ruff_json(self) -> None:
        from quality_gate import _collect_lint_fingerprints

        fake = _fake_run_factory(
            rules=[
                (
                    ("check", "--output-format=json"),
                    1,
                    _ruff_json([("src/a.py", "F401"), ("src/b.py", "E501")]),
                )
            ]
        )
        with patch("quality_gate._run", side_effect=fake):
            fps = _collect_lint_fingerprints()
        assert fps == {("lint", "src/a.py", "F401"), ("lint", "src/b.py", "E501")}

    def test_lint_collector_null_code_maps_to_syntax_error(self) -> None:
        import json

        from quality_gate import _collect_lint_fingerprints

        payload = json.dumps([{"filename": "src/bad.py", "code": None}])
        fake = _fake_run_factory(rules=[(("--output-format=json",), 1, payload)])
        with patch("quality_gate._run", side_effect=fake):
            fps = _collect_lint_fingerprints()
        assert fps == {("lint", "src/bad.py", "syntax-error")}

    def test_lint_collector_unparseable_json_fails_closed(self) -> None:
        """Garbage ruff output must not read as an empty (clean) finding set."""
        from quality_gate import _collect_lint_fingerprints

        fake = _fake_run_factory(rules=[(("--output-format=json",), 2, "ruff exploded")])
        with patch("quality_gate._run", side_effect=fake):
            fps = _collect_lint_fingerprints()
        assert fps  # non-empty sentinel → cannot match any baseline → RED


class TestCheckAgainstBaseline:
    """_check_against_baseline — set membership, never count (F2 / AC1 / AC2)."""

    _A = ("lint", "src/a.py", "F401")
    _B = ("lint", "src/b.py", "E501")
    _C = ("lint", "src/c.py", "F841")
    _D = ("lint", "src/d.py", "F811")

    def test_baselined_findings_warn_and_pass(self, capsys: pytest.CaptureFixture) -> None:
        """AC1: findings in the baseline WARN with a count and do not fail."""
        from quality_gate import _check_against_baseline

        ok = _check_against_baseline(
            "lint", "Linting (ruff check)", {self._A, self._B}, {self._A, self._B, self._C}, "hint"
        )
        captured = capsys.readouterr()
        assert ok is True
        assert "2 baselined debt item(s)" in captured.out
        assert "WARN lint: 2 baselined debt item(s)" in captured.err

    def test_new_finding_fails_naming_only_the_new_fingerprint(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """AC1: the ERROR line names the NEW finding, not the baselined ones."""
        from quality_gate import _check_against_baseline

        ok = _check_against_baseline(
            "lint",
            "Linting (ruff check)",
            {self._A, self._B, self._D},
            {self._A, self._B},
            "hint",
        )
        captured = capsys.readouterr()
        assert ok is False
        error_lines = [ln for ln in captured.err.splitlines() if ln.startswith("ERROR lint: ")]
        assert len(error_lines) == 1
        assert "src/d.py" in error_lines[0]
        assert "src/a.py" not in error_lines[0]
        assert "src/b.py" not in error_lines[0]

    @pytest.mark.regression
    def test_one_for_one_swap_fails_despite_equal_counts(self) -> None:
        """AC2 (security F2): {A,B,D} vs baseline {A,B,C} — counts equal (3),
        but D is new → RED. A count-based compare would pass this."""
        from quality_gate import _check_against_baseline

        ok = _check_against_baseline(
            "lint",
            "Linting (ruff check)",
            {self._A, self._B, self._D},
            {self._A, self._B, self._C},
            "hint",
        )
        assert ok is False

    def test_clean_current_passes_plainly(self, capsys: pytest.CaptureFixture) -> None:
        from quality_gate import _check_against_baseline

        ok = _check_against_baseline("lint", "Linting (ruff check)", set(), {self._A}, "hint")
        assert ok is True
        assert "PASS" in capsys.readouterr().out


class TestFastSelection:
    """_select_fast_tests — deterministic, content-independent (R3.3 / AC8)."""

    def _make_tests(self, tmp_path: Path, n: int) -> Path:
        d = tmp_path / "tests"
        d.mkdir(exist_ok=True)
        for i in range(n):
            (d / f"test_{chr(97 + i)}.py").write_text(
                "def test_x():\n    pass\n", encoding="utf-8"
            )
        return d

    def test_same_file_list_yields_same_subset(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import quality_gate as qg

        monkeypatch.setattr(qg, "TESTS_DIR", self._make_tests(tmp_path, 8))
        first = qg._select_fast_tests()
        second = qg._select_fast_tests()
        assert first == second
        assert len(first) == 2  # ceil(8/4) — stride-4 over the sorted list

    def test_subset_changes_only_when_file_list_changes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import quality_gate as qg

        tests_dir = self._make_tests(tmp_path, 8)
        monkeypatch.setattr(qg, "TESTS_DIR", tests_dir)
        before = qg._select_fast_tests()
        (tests_dir / "test_aa.py").write_text("def test_y():\n    pass\n", encoding="utf-8")
        after = qg._select_fast_tests()
        assert before != after  # list changed → subset may change
        assert after == qg._select_fast_tests()  # ...but stays deterministic

    @pytest.mark.parametrize("n,expected", [(0, 0), (1, 1), (4, 1), (5, 2), (12, 3)])
    def test_sample_size_is_quarter_stride(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, n: int, expected: int
    ) -> None:
        import quality_gate as qg

        monkeypatch.setattr(qg, "TESTS_DIR", self._make_tests(tmp_path, n))
        assert len(qg._select_fast_tests()) == expected

    @pytest.mark.regression  # qa checkpoint fix, 2026-07-17
    def test_empty_sample_never_falls_back_to_full_discovery(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """qa checkpoint (2026-07-17): fast_files=[] must not invoke pytest
        with no path args (full-suite discovery)."""
        from quality_gate import check_tests

        calls: list = []
        fake = _fake_run_factory(record=calls)
        with patch("quality_gate._run", side_effect=fake):
            ok = check_tests(fast_files=[])
        assert ok is True
        assert calls == []  # pytest never invoked
        assert "no test files found to sample" in capsys.readouterr().err


class TestFastIsNeverACommitGate:
    """F5 / AC8: a sampled run must never stand in as commit-time verification."""

    def test_pre_commit_hook_never_passes_fast(self) -> None:
        hook_text = _PRE_COMMIT_HOOK.read_text(encoding="utf-8")
        assert "--fast" not in hook_text
        # Sanity: the verification cache does live in the hook layer…
        assert "commit-verified" in hook_text

    def test_gate_source_never_writes_the_verification_cache(self) -> None:
        """…and the gate script references it only in comments (the F5 guard),
        never in executable code."""
        source = (_REPO_ROOT / "scripts" / "quality_gate.py").read_text(encoding="utf-8")
        for line in source.splitlines():
            if "commit-verified" in line:
                assert line.lstrip().startswith("#"), (
                    "quality_gate.py must never touch the pre-commit "
                    f"verification cache in code: {line!r}"
                )


class TestShippedProfilesYaml:
    """The committed config/gate_profiles.yaml must mirror the built-ins.

    File-declared profiles shadow built-ins wholesale, so silent drift between
    the two would change behavior depending on whether the file is present —
    exactly the fork-per-project failure mode this spec retires.
    """

    def test_shipped_yaml_matches_builtin_profiles(self) -> None:
        import quality_gate as qg

        data = qg._load_profiles_config(_REPO_ROOT / "config" / "gate_profiles.yaml")
        assert data["schema_version"] == 1
        assert data["profiles"] == qg._BUILTIN_PROFILES

    def test_shipped_yaml_has_no_profile_pin(self) -> None:
        """The template auto-detects; the pin is SKIN for derived projects."""
        import quality_gate as qg

        data = qg._load_profiles_config(_REPO_ROOT / "config" / "gate_profiles.yaml")
        assert data.get("profile") is None


class TestMachineLineConventions:
    """R3.1: one-line greppable ERROR/WARN convention, ASCII-safe."""

    def test_one_line_collapses_and_asciifies(self) -> None:
        from quality_gate import _one_line

        out = _one_line("multi\nline — reason\twith tabs")
        assert "\n" not in out and "\t" not in out
        out.encode("ascii")
        out.encode("cp1252")

    def test_emit_error_line_shape(self, capsys: pytest.CaptureFixture) -> None:
        import re

        from quality_gate import _emit_error_line

        _emit_error_line("lint", "2 new finding(s)")
        err = capsys.readouterr().err
        assert re.search(r"^ERROR \w+: ", err, re.MULTILINE)
        err.encode("cp1252")

    def test_emit_warn_line_shape(self, capsys: pytest.CaptureFixture) -> None:
        import re

        from quality_gate import _emit_warn_line

        _emit_warn_line("baseline", "3 baselined debt item(s)")
        err = capsys.readouterr().err
        assert re.search(r"^WARN \w+: ", err, re.MULTILINE)


class TestReviewGateCoversGateConfig:
    """AC3b (security F1): gate config files are review-gated staged paths."""

    @staticmethod
    def _staged(stdout: str):
        import subprocess as sp

        def fake(cmd, **kwargs):  # noqa: ANN001
            return sp.CompletedProcess(cmd, 0, stdout=stdout, stderr="")

        return fake

    def test_staged_gate_config_files_count_as_code_changes(self) -> None:
        from quality_gate import _get_staged_code_files

        stdout = "config/gate_baseline.json\nconfig/gate_profiles.yaml\nREADME.md\n"
        with patch("quality_gate.subprocess.run", side_effect=self._staged(stdout)):
            files = _get_staged_code_files()
        assert "config/gate_baseline.json" in files
        assert "config/gate_profiles.yaml" in files
        assert "README.md" not in files

    @pytest.mark.regression
    def test_staged_baseline_without_review_fails_the_check(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """A direct (out-of-band) baseline edit cannot commit unreviewed."""
        from quality_gate import check_review_existence

        with (
            patch(
                "quality_gate._get_staged_code_files",
                return_value=["config/gate_baseline.json"],
            ),
            patch("quality_gate._find_todays_reviews", return_value=[]),
        ):
            ok = check_review_existence()
        assert ok is False
        assert "ERROR reviews: " in capsys.readouterr().err


class TestMainProfileRuns:
    """main()-level integration for AC4/AC5/AC6/AC7/AC8/AC9."""

    _FLUTTER_PROFILES_YAML = (
        "schema_version: 1\n"
        "profiles:\n"
        "  flutter-dart:\n"
        "    checks:\n"
        "      format:\n"
        "        enabled: true\n"
        '        command: [dart, format, --output=none, --set-exit-if-changed, "."]\n'
        "      lint: {enabled: true, command: [dart, analyze]}\n"
        "      tests: {enabled: true, command: [flutter, test]}\n"
        "      coverage: {enabled: false}\n"
        "      reviews: {enabled: false}\n"  # integrity-disable attempt (F4)
    )

    def test_zero_config_run_matches_golden_fixture(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """AC6: no config file, no flags, python-fastapi auto-detected → the
        stdout summary structure matches the fixture captured from pre-change
        main (tests/fixtures/gate_summary_golden.txt) and the gate is green."""
        qg = _gate_env(monkeypatch, tmp_path)  # pyproject marker, no config files
        exit_code = _run_gate(qg, monkeypatch, [], _fake_run_factory())
        captured = capsys.readouterr()
        assert exit_code == 0
        # The fixture was captured raw from a Windows console: its WARN lines
        # carry cp1252 em-dash bytes. Tolerant read is fine — the normalizer
        # drops WARN lines on both sides.
        golden = _normalize_gate_stdout(
            _GOLDEN_FIXTURE.read_text(encoding="utf-8", errors="replace")
        )
        live = _normalize_gate_stdout(captured.out)
        assert live == golden
        assert "profile: python-fastapi (auto-detected: pyproject.toml)" in captured.err

    def test_flutter_profile_invokes_dart_never_ruff(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """AC5: flutter-dart runs dart/flutter argv lists via the _run seam,
        never ruff/pytest; integrity checks still run; the profile's attempt to
        disable 'reviews' has no effect; baseline emits the R1.0 WARN."""
        qg = _gate_env(
            monkeypatch,
            tmp_path,
            profiles=self._FLUTTER_PROFILES_YAML,
            baseline=_baseline_json([("lint", "src/a.py", "F401")]),
        )
        calls: list = []
        exit_code = _run_gate(
            qg, monkeypatch, ["--profile", "flutter-dart"], _fake_run_factory(record=calls)
        )
        captured = capsys.readouterr()
        joined = [" ".join(c) for c in calls]
        assert exit_code == 0
        assert any(c.startswith("dart format") for c in joined)
        assert any(c.startswith("dart analyze") for c in joined)
        assert any(c.startswith("flutter test") for c in joined)
        assert not any("ruff" in c or "pytest" in c for c in joined)
        # Integrity checks ran despite the profile's disable attempt (F4)
        assert "ADR completeness" in captured.out
        assert "Review existence" in captured.out
        assert "ignoring unknown check key 'reviews'" in captured.err
        # R1.0: baseline unsupported on this profile — WARN, never a crash
        assert "WARN baseline: not supported for profile flutter-dart" in captured.err
        record = _read_log(tmp_path)
        assert record["profile"] == "flutter-dart"
        assert record["checks"]["coverage"] == "disabled"
        assert record["checks"]["reviews"] == "pass"
        assert record["overall"] == "pass"

    def test_markdown_corpus_runs_only_corpus_checks(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """AC5: markdown-corpus disables every stack check (no _run calls at
        all) but still runs the integrity checks and can reach a clean pass."""
        qg = _gate_env(monkeypatch, tmp_path, marker=None)
        calls: list = []
        exit_code = _run_gate(
            qg, monkeypatch, ["--profile", "markdown-corpus"], _fake_run_factory(record=calls)
        )
        captured = capsys.readouterr()
        assert exit_code == 0
        assert calls == []  # no stack commands executed
        assert "disabled by profile markdown-corpus" in captured.out
        assert "ADR completeness" in captured.out
        record = _read_log(tmp_path)
        assert record["overall"] == "pass"
        assert record["checks"]["format"] == "disabled"

    def test_config_pin_selects_profile(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """AC4: the config 'profile:' pin wins over auto-detect."""
        qg = _gate_env(
            monkeypatch,
            tmp_path,
            profiles="schema_version: 1\nprofile: markdown-corpus\n",
        )
        exit_code = _run_gate(qg, monkeypatch, [], _fake_run_factory())
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "profile: markdown-corpus (config pin)" in captured.err

    @pytest.mark.parametrize(
        "argv,profiles",
        [
            (["--profile", "bogus"], None),  # unknown name
            ([], "{"),  # malformed file
            ([], ""),  # present-but-empty file (qa 5)
        ],
    )
    def test_bad_profile_config_fails_closed_without_logging(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
        argv: list[str],
        profiles: str | None,
    ) -> None:
        """AC4: unknown/malformed/empty profile config → one ERROR profile:
        line, non-zero exit, and no gate-log record (nothing was verified)."""
        import re

        qg = _gate_env(monkeypatch, tmp_path, profiles=profiles)
        exit_code = _run_gate(qg, monkeypatch, argv, _fake_run_factory())
        captured = capsys.readouterr()
        assert exit_code == 1
        assert len(re.findall(r"^ERROR profile: ", captured.err, re.MULTILINE)) == 1
        assert not (tmp_path / "metrics" / "gate_log.jsonl").exists()

    def test_corrupt_baseline_fails_closed_at_main_level(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """AC3a: an invalid baseline file aborts the run RED, never runs checks."""
        qg = _gate_env(monkeypatch, tmp_path, baseline="definitely not json")
        exit_code = _run_gate(qg, monkeypatch, [], _fake_run_factory())
        captured = capsys.readouterr()
        assert exit_code == 1
        assert "ERROR baseline: " in captured.err
        assert not (tmp_path / "metrics" / "gate_log.jsonl").exists()


class TestMainBaselineFlows:
    """main()-level baseline mechanics: AC1, AC2, AC3."""

    _BASE = [
        ("lint", "src/a.py", "F401"),
        ("lint", "src/b.py", "E501"),
        ("lint", "src/c.py", "F841"),
    ]

    @staticmethod
    def _ruff_rules(lint_entries: list[tuple[str, str]], reformat: list[str] | None = None):
        """_run rules: clean format check (or Would-reformat lines), lint JSON,
        passing pytest/coverage."""
        reformat_out = "".join(f"Would reformat: {f}\n" for f in reformat or [])
        return [
            (("format", "--check"), 1 if reformat else 0, reformat_out),
            (
                ("check", "--output-format=json"),
                1 if lint_entries else 0,
                _ruff_json(lint_entries),
            ),
            (("check",), 0, ""),  # plain ruff check (non-baseline path)
        ]

    def test_baselined_debt_warns_and_gate_passes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """AC1 first half: 3 pre-existing violations in the baseline → WARN
        with count=3, gate green, debt count in the log."""
        qg = _gate_env(monkeypatch, tmp_path, baseline=_baseline_json(self._BASE))
        fake = _fake_run_factory(rules=self._ruff_rules([(f, c) for _, f, c in self._BASE]))
        exit_code = _run_gate(qg, monkeypatch, [], fake)
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "3 baselined debt item(s)" in captured.out
        record = _read_log(tmp_path)
        assert record["baseline_debt_count"] == 3
        assert record["overall"] == "pass"

    def test_new_violation_fails_red_naming_only_the_new_fingerprint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """AC1 second half: baseline + 1 new violation → RED; ERROR lint names
        only the new fingerprint; the baseline file is NOT grown."""
        qg = _gate_env(monkeypatch, tmp_path, baseline=_baseline_json(self._BASE))
        before = (tmp_path / "gate_baseline.json").read_bytes()
        lint_now = [(f, c) for _, f, c in self._BASE] + [("src/new.py", "F811")]
        exit_code = _run_gate(
            qg, monkeypatch, [], _fake_run_factory(rules=self._ruff_rules(lint_now))
        )
        captured = capsys.readouterr()
        assert exit_code == 1
        error_lines = [ln for ln in captured.err.splitlines() if ln.startswith("ERROR lint: ")]
        assert len(error_lines) == 1
        assert "src/new.py" in error_lines[0]
        assert "src/a.py" not in error_lines[0]
        assert (tmp_path / "gate_baseline.json").read_bytes() == before  # never grown

    @pytest.mark.regression
    def test_swap_fails_red_at_main_level(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC2 (F2): {A,B,D} vs baseline {A,B,C} — equal counts, still RED."""
        qg = _gate_env(monkeypatch, tmp_path, baseline=_baseline_json(self._BASE))
        lint_now = [("src/a.py", "F401"), ("src/b.py", "E501"), ("src/d.py", "F811")]
        exit_code = _run_gate(
            qg, monkeypatch, [], _fake_run_factory(rules=self._ruff_rules(lint_now))
        )
        assert exit_code == 1

    def test_burn_down_reported_but_not_applied_without_flag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """AC2: current ⊂ baseline → burn-down reported, file unchanged."""
        qg = _gate_env(monkeypatch, tmp_path, baseline=_baseline_json(self._BASE))
        before = (tmp_path / "gate_baseline.json").read_bytes()
        lint_now = [("src/a.py", "F401"), ("src/b.py", "E501")]  # c.py resolved
        exit_code = _run_gate(
            qg, monkeypatch, [], _fake_run_factory(rules=self._ruff_rules(lint_now))
        )
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "1 item(s) resolved" in captured.out
        assert (tmp_path / "gate_baseline.json").read_bytes() == before

    def test_shrink_baseline_ratchets_down(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """AC2: --shrink-baseline rewrites the baseline to the remaining set."""
        from quality_gate import _load_baseline

        qg = _gate_env(monkeypatch, tmp_path, baseline=_baseline_json(self._BASE))
        lint_now = [("src/a.py", "F401"), ("src/b.py", "E501")]
        exit_code = _run_gate(
            qg,
            monkeypatch,
            ["--shrink-baseline"],
            _fake_run_factory(rules=self._ruff_rules(lint_now)),
        )
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "shrunk by 1 resolved item(s)" in captured.out
        assert _load_baseline(tmp_path / "gate_baseline.json") == {
            ("lint", "src/a.py", "F401"),
            ("lint", "src/b.py", "E501"),
        }

    def test_shrink_does_not_fire_alongside_new_findings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R1.3: ratchet only from a clean state (current ⊂ baseline) — with a
        new finding present the gate is RED and the baseline stays untouched."""
        qg = _gate_env(monkeypatch, tmp_path, baseline=_baseline_json(self._BASE))
        before = (tmp_path / "gate_baseline.json").read_bytes()
        lint_now = [("src/a.py", "F401"), ("src/new.py", "F811")]  # b,c resolved + 1 new
        exit_code = _run_gate(
            qg,
            monkeypatch,
            ["--shrink-baseline"],
            _fake_run_factory(rules=self._ruff_rules(lint_now)),
        )
        assert exit_code == 1
        assert (tmp_path / "gate_baseline.json").read_bytes() == before

    # NOTE: the former ``test_rebaseline_writes_notice_and_log_flag`` (AC3) drove
    # ``--rebaseline`` end-to-end through main() and asserted that it WROTE the
    # baseline. That assertion had to go — --rebaseline no longer writes. What
    # must NOT go with it is CLI-level coverage of the flag: see
    # TestRebaselineWritesNothingThroughMain below, which drives the same path
    # and asserts the opposite outcome. TestBaselineCannotGrow pins the wider
    # property (*no* flag combination can grow the baseline) on the pure
    # decision function; neither class substitutes for the other.


class TestRebaselineWritesNothingThroughMain:
    """CLI-level proof of this script's headline guarantee.

    ``scripts/quality_gate.py``'s module docstring and ``_baseline_write_plan``
    both claim that *no invocation of this script — no flag, no combination of
    flags — can add a fingerprint to config/gate_baseline.json*. That is a claim
    about ``main()``.

    For one day (2026-08-07 → 2026-08-08) it was pinned only by unit tests on
    the pure helper, and ``main()``'s ``--rebaseline`` branch was executed by
    **zero** tests: ``grep -n '"--rebaseline"' tests/*.py`` returned nothing. A
    Round-2 critic proved the consequence by restoring the literal pre-fix
    defect — ``_write_baseline(current_fps)`` immediately after
    ``_print_baseline_proposal(current_fps)`` in ``main()`` — and measuring the
    suite: 163 passed, exit 0. The guard had been moved out of a test and into a
    docstring, which is the same "prose asserting more than the code enforces"
    failure the change existed to remove.

    Every test in this class drives the real ``main()`` with real argv inside the
    ``_gate_env`` tmp_path sandbox (``GATE_BASELINE_FILE`` is repointed, so even
    a reintroduced write lands in tmp, never in the repo), and every one of them
    goes RED under that exact mutation. Re-prove it the way the critic did:

        # in a SCRATCH copy of the tree, never the repo:
        #   add `_write_baseline(current_fps)` after `_print_baseline_proposal(...)`
        python -m pytest tests/test_quality_gate.py -q   # must be RED

    Each test also asserts the proposal actually printed, so none of them can
    pass vacuously by never reaching the ``--rebaseline`` branch at all.
    """

    _BASE = [("lint", "src/a.py", "F401"), ("lint", "src/b.py", "E501")]

    @pytest.mark.regression
    def test_rebaseline_through_main_creates_no_baseline_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """--rebaseline on a repo with no baseline file must not create one.

        This is the shape the reward-function risk actually takes: the file does
        not exist in this template or in any of the four derived projects, so
        "grow the baseline" means "conjure it from whatever the tree emits".
        """
        import json

        qg = _gate_env(monkeypatch, tmp_path)  # no baseline file
        lint_now = [("src/a.py", "F401"), ("src/new.py", "F811")]
        exit_code = _run_gate(
            qg,
            monkeypatch,
            ["--rebaseline"],
            _fake_run_factory(rules=TestMainBaselineFlows._ruff_rules(lint_now)),
        )
        captured = capsys.readouterr()

        assert not (tmp_path / "gate_baseline.json").exists(), (
            "--rebaseline wrote config/gate_baseline.json through main() — the "
            "gate grew its own reward function"
        )
        # Non-vacuity: the branch really ran and really held the fingerprints a
        # write would have persisted.
        assert "nothing was written" in captured.out
        # The proposal is followed by the rest of the gate's stdout, so decode
        # only the leading JSON object rather than the whole tail.
        payload, _ = json.JSONDecoder().raw_decode(captured.out[captured.out.index("{") :])
        assert {(f["check"], f["file"], f["code"]) for f in payload["fingerprints"]} == {
            ("lint", "src/a.py", "F401"),
            ("lint", "src/new.py", "F811"),
        }
        assert exit_code == 1  # src/new.py is un-baselined debt: still RED
        assert _read_log(tmp_path)["rebaseline"] is True

    @pytest.mark.regression
    def test_rebaseline_through_main_leaves_an_existing_baseline_byte_identical(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """--rebaseline over an existing baseline must not rewrite it.

        ``current`` here holds a fingerprint the baseline does not, so the
        pre-2026-08-07 overwrite would be visible as a byte change *and* as a
        grown fingerprint set — not merely as a re-serialization.
        """
        qg = _gate_env(monkeypatch, tmp_path, baseline=_baseline_json(self._BASE))
        target = tmp_path / "gate_baseline.json"
        before = target.read_bytes()
        lint_now = [("src/a.py", "F401"), ("src/new.py", "F811")]
        _run_gate(
            qg,
            monkeypatch,
            ["--rebaseline"],
            _fake_run_factory(rules=TestMainBaselineFlows._ruff_rules(lint_now)),
        )
        captured = capsys.readouterr()

        assert target.read_bytes() == before, "--rebaseline rewrote the baseline through main()"
        assert qg._load_baseline(target) == {
            ("lint", "src/a.py", "F401"),
            ("lint", "src/b.py", "E501"),
        }
        assert "nothing was written" in captured.out  # non-vacuity
        assert "src/new.py" in captured.out  # the fingerprint a write would have added

    @pytest.mark.regression
    @pytest.mark.parametrize(
        "lint_now,reformat",
        [
            ([], None),  # everything fixed
            ([("src/a.py", "F401")], None),  # subset of the baseline
            ([("src/a.py", "F401"), ("src/new.py", "F811")], None),  # one new
            ([("src/new.py", "F811")], ["src/z.py"]),  # all new, both checks
        ],
        ids=["all-fixed", "subset", "one-new", "all-new"],
    )
    def test_no_cli_flag_combination_grows_the_baseline_through_main(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
        lint_now: list[tuple[str, str]],
        reformat: list[str] | None,
    ) -> None:
        """The docstring's exact words, executed. Two distinct guarantees:

        * for **all 8** flag combinations, the baseline on disk is never a
          superset of the one that was there before ("cannot grow");
        * for the **4 combinations containing --rebaseline**, the file is
          byte-identical afterwards ("proposes only — writes nothing"). That is
          the stronger claim, and it needs its own assertion: a mutation that
          lets ``--rebaseline --shrink-baseline`` write a *shrunk* baseline
          satisfies the first and violates the second.
        """
        original = {("lint", f, c) for _, f, c in self._BASE}
        for rebaseline in (False, True):
            for fix in (False, True):
                for shrink in (False, True):
                    sub = tmp_path / f"r{int(rebaseline)}f{int(fix)}s{int(shrink)}"
                    sub.mkdir()
                    qg = _gate_env(monkeypatch, sub, baseline=_baseline_json(self._BASE))
                    target = sub / "gate_baseline.json"
                    before = target.read_bytes()
                    argv = [
                        *(["--rebaseline"] if rebaseline else []),
                        *(["--fix"] if fix else []),
                        *(["--shrink-baseline"] if shrink else []),
                    ]
                    _run_gate(
                        qg,
                        monkeypatch,
                        argv,
                        _fake_run_factory(
                            rules=TestMainBaselineFlows._ruff_rules(lint_now, reformat)
                        ),
                    )
                    out = capsys.readouterr().out
                    after = qg._load_baseline(target)
                    assert after <= original, (
                        f"{argv or ['(no flags)']} grew the baseline: {after - original}"
                    )
                    if rebaseline:
                        assert target.read_bytes() == before, (
                            f"{argv} wrote the baseline — --rebaseline proposes only"
                        )
                        # Non-vacuity: the --rebaseline branch really executed.
                        assert "nothing was written" in out


class TestWhichPathRunsWhenNoBaselineFileExists:
    """Which code path format/lint take when ``config/gate_baseline.json`` is absent.

    Three write-ups around this mechanism — ``scripts/quality_gate.py``'s module
    docstring, ``config/gate_profiles.yaml``, and Row 5 of
    ``docs/education/governance-mechanisms.md`` — each said that with no
    baseline file the format and lint checks "take their ordinary path" and
    ``_check_against_baseline`` "never runs" / "has never run outside its
    tests", and concluded the comparison is an *entirely unexercised*
    mechanism.

    Measured 2026-08-08: true for an ordinary run, **false for**
    ``--rebaseline`` — which is the one invocation those three paragraphs are
    about. ``current_fps`` is collected whenever ``baseline or
    args.rebaseline``, and a non-``None`` ``current_fps`` routes both checks
    through ``_check_against_baseline`` against an **empty** baseline, where
    every finding is reported as "NEW finding(s) not in baseline" even though
    no baseline exists.

    The code was the honest artifact and the prose was not — the sibling test
    ``test_rebaseline_through_main_creates_no_baseline_file`` already asserted
    ``exit_code == 1`` "still RED", an outcome only reachable through the very
    comparison the prose said never runs. Both halves of the corrected claim
    are pinned below so it cannot drift back into an assertion: **the ordinary
    run really does take the ordinary path, and ``--rebaseline`` really does
    not.**
    """

    @staticmethod
    def _spy(monkeypatch: pytest.MonkeyPatch, qg, name: str, log: list[str]):
        """Wrap a module-level check so calls are recorded but behaviour is unchanged."""
        original = getattr(qg, name)

        def recording(*args, **kwargs):
            log.append(name if name != "_check_against_baseline" else f"{name}:{args[0]}")
            return original(*args, **kwargs)

        monkeypatch.setattr(qg, name, recording)

    @pytest.mark.regression
    def test_rebaseline_with_no_baseline_file_runs_the_comparison_on_an_empty_baseline(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """THE corrected claim. ``--rebaseline`` + no baseline file ⇒ the
        comparison runs, and its RED text says "not in baseline" when there is
        no baseline at all."""
        qg = _gate_env(monkeypatch, tmp_path)  # no baseline file
        assert not (tmp_path / "gate_baseline.json").exists()
        calls: list[str] = []
        for name in ("_check_against_baseline", "check_formatting", "check_linting"):
            self._spy(monkeypatch, qg, name, calls)

        exit_code = _run_gate(
            qg,
            monkeypatch,
            ["--rebaseline"],
            _fake_run_factory(
                rules=TestMainBaselineFlows._ruff_rules([("src/a.py", "F401")], ["src/z.py"])
            ),
        )
        captured = capsys.readouterr()

        assert calls == ["_check_against_baseline:format", "_check_against_baseline:lint"], (
            "with --rebaseline the comparison runs for BOTH stack checks and the "
            f"ordinary check_formatting/check_linting path is not taken; got {calls}"
        )
        # The empty baseline makes every finding read as NEW — the wording is a
        # known wart, recorded here rather than described as impossible.
        assert "NEW finding(s) not in baseline" in captured.out
        assert exit_code == 1
        assert not (tmp_path / "gate_baseline.json").exists()

    @pytest.mark.regression
    def test_ordinary_run_with_no_baseline_file_takes_the_ordinary_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """The half of the old claim that IS true — kept as the contrast that
        makes the corrected wording precise rather than merely narrower."""
        qg = _gate_env(monkeypatch, tmp_path)  # no baseline file, no --rebaseline
        calls: list[str] = []
        for name in ("_check_against_baseline", "check_formatting", "check_linting"):
            self._spy(monkeypatch, qg, name, calls)

        exit_code = _run_gate(qg, monkeypatch, [], _fake_run_factory())
        captured = capsys.readouterr()

        assert calls == ["check_formatting", "check_linting"], (
            f"without --rebaseline the comparison must not run; got {calls}"
        )
        assert exit_code == 0
        # Non-vacuity: the two checks really produced their ordinary output.
        assert "Formatting (ruff format)" in captured.out
        assert "Linting (ruff check)" in captured.out


class TestBaselineCannotGrow:
    """The debt baseline is the gate's reward function: prove the gate cannot grow it.

    Until 2026-08-07 ``--rebaseline`` called ``_write_baseline(current_fps)`` —
    an unconditional overwrite — and the only thing standing between an
    autonomous agent and re-cutting its own pass/fail criterion was a sentence
    in an argparse help string asking it not to. A rule addressed to the actor
    it is meant to bind, enforced by nothing, is not a control.

    These tests exercise ``_baseline_write_plan``, the single decision point for
    every write, rather than the CLI: the invariant worth pinning is a property
    of *all* flag combinations, which one end-to-end run cannot establish.
    """

    _BASELINE = {("lint", "src/a.py", "F401"), ("lint", "src/b.py", "E501")}

    @staticmethod
    def _flag_combos() -> list[dict[str, bool]]:
        return [
            {"rebaseline": r, "fix": f, "shrink": s}
            for r in (False, True)
            for f in (False, True)
            for s in (False, True)
        ]

    @pytest.mark.regression
    @pytest.mark.parametrize(
        "current",
        [
            set(),  # everything fixed
            {("lint", "src/a.py", "F401")},  # subset
            {("lint", "src/a.py", "F401"), ("lint", "src/new.py", "F811")},  # new debt
            {("lint", "src/new.py", "F811"), ("format", "src/z.py", "reformat")},  # all new
        ],
        ids=["all-fixed", "subset", "one-new", "all-new"],
    )
    def test_no_flag_combination_can_grow_the_baseline(self, current: set) -> None:
        """THE invariant: every set the gate may persist is a subset of the
        baseline that already exists — for all 8 flag combinations."""
        from quality_gate import _baseline_write_plan

        for flags in self._flag_combos():
            plan = _baseline_write_plan(baseline=self._BASELINE, current=current, **flags)
            if plan is None:
                continue
            assert plan <= self._BASELINE, f"{flags} grew the baseline: {plan - self._BASELINE}"

    @pytest.mark.regression
    @pytest.mark.parametrize(
        "current",
        [
            {("lint", "src/new.py", "F811")},  # new debt present
            {("lint", "src/a.py", "F401")},  # resolved debt present, NO new debt
            set(),  # everything resolved
        ],
        ids=["new-debt", "resolved-debt", "all-resolved"],
    )
    def test_rebaseline_never_writes_whatever_else_is_passed(self, current: set) -> None:
        """--rebaseline proposes only. It cannot write, even combined with the
        flags that legitimately do (this is the pre-2026-08-07 defect).

        The ``current`` parametrization is load-bearing and was added 2026-08-08.
        The original test passed only ``{new debt}``, where ``_resolved_debt``
        returns empty and the plan is ``None`` for a *different* reason — so
        deleting the ``if rebaseline: return None`` veto outright left this test
        green (measured: mutation 2, 169/169 passed). The two subset cases make
        the veto the only thing standing between ``--rebaseline --shrink-baseline``
        and a write. "Cannot GROW the baseline" and "writes NOTHING" are two
        different guarantees; the docstring makes both, so both are pinned.
        """
        from quality_gate import _baseline_write_plan

        for fix, shrink in ((False, False), (True, False), (False, True), (True, True)):
            assert (
                _baseline_write_plan(
                    rebaseline=True,
                    fix=fix,
                    shrink=shrink,
                    baseline=self._BASELINE,
                    current=current,
                )
                is None
            ), f"--rebaseline wrote with fix={fix}, shrink={shrink}, current={current}"

    def test_shrink_plan_is_the_surviving_intersection(self) -> None:
        """--shrink-baseline ratchets down to exactly the remaining findings."""
        from quality_gate import _baseline_write_plan

        plan = _baseline_write_plan(
            rebaseline=False,
            fix=False,
            shrink=True,
            baseline=self._BASELINE,
            current={("lint", "src/a.py", "F401")},
        )
        assert plan == {("lint", "src/a.py", "F401")}

    def test_new_findings_block_the_ratchet(self) -> None:
        """R1.3: with NEW debt present nothing is written — the gate is red and
        the fix is to clear the new debt, not to re-cut the baseline round it."""
        from quality_gate import _baseline_write_plan

        assert (
            _baseline_write_plan(
                rebaseline=False,
                fix=True,
                shrink=True,
                baseline=self._BASELINE,
                current={("lint", "src/a.py", "F401"), ("lint", "src/new.py", "F811")},
            )
            is None
        )

    def test_nothing_written_without_fix_or_shrink(self) -> None:
        """An ordinary run never touches the baseline, even when debt is fixed."""
        from quality_gate import _baseline_write_plan

        assert (
            _baseline_write_plan(
                rebaseline=False, fix=False, shrink=False, baseline=self._BASELINE, current=set()
            )
            is None
        )

    def test_proposal_prints_the_payload_and_writes_no_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """--rebaseline's printer emits committable JSON and creates no file."""
        import json

        import quality_gate as qg

        target = tmp_path / "gate_baseline.json"
        monkeypatch.setattr(qg, "GATE_BASELINE_FILE", target)
        qg._print_baseline_proposal({("lint", "src/a.py", "F401")})
        captured = capsys.readouterr()

        assert not target.exists(), "the proposal must not write the baseline"
        assert "nothing was written" in captured.out
        payload = json.loads(captured.out[captured.out.index("{") :])
        assert payload["fingerprints"] == [{"check": "lint", "file": "src/a.py", "code": "F401"}]


class TestMainErgonomics:
    """AC7 (one ERROR line per failing check) and AC8 (--fast semantics)."""

    def test_every_failing_check_emits_exactly_one_error_line(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """AC7: force all seven checks to fail → exactly one greppable
        ``^ERROR <check>: `` line each."""
        import re

        qg = _gate_env(monkeypatch, tmp_path)
        # Fail the four stack checks through the seam…
        fake = _fake_run_factory(
            rules=[
                (("format", "--check"), 1, "Would reformat: src/x.py"),
                (("pytest", "--cov"), 1, "FAILED"),
                (("pytest",), 1, "FAILED tests/test_x.py"),
                (("check",), 1, "src/x.py:1:1: F401 unused import"),
            ]
        )
        # …and the three integrity checks through their own inputs.
        adr_dir = tmp_path / "adrs"
        adr_dir.mkdir()
        (adr_dir / "ADR-9999-bad.md").write_text("no frontmatter here", encoding="utf-8")
        monkeypatch.setattr(qg, "ADR_DIR", adr_dir)
        ledger = tmp_path / "ledger.md"
        ledger.write_text(
            "| File | Bug Description | Root Cause Class | Fix Date | Test File "
            "| Test Function |\n"
            "|------|---|---|---|---|---|\n"
            "| src/foo.py | d | Missing Null | 2026-01-01 | tests/test_gone.py | test_x |\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(qg, "REGRESSION_LEDGER", ledger)
        monkeypatch.setattr(qg, "_get_staged_code_files", lambda: ["src/x.py"])
        monkeypatch.setattr(qg, "_find_todays_reviews", lambda: [])

        exit_code = _run_gate(qg, monkeypatch, [], fake)
        err = capsys.readouterr().err
        assert exit_code == 1
        for check in ["format", "lint", "tests", "coverage", "adrs", "reviews", "regression"]:
            matches = re.findall(rf"^ERROR {check}: ", err, re.MULTILINE)
            assert len(matches) == 1, f"{check}: expected exactly 1 ERROR line, got {matches}"
        # Every ERROR line matches the documented greppable shape.
        for line in err.splitlines():
            if line.startswith("ERROR"):
                assert re.match(r"^ERROR \w+: ", line), line

    def test_missing_python_dirs_fail_closed_with_setup_error_line(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """qa review (2026-07-17): the new needs_python_dirs bail path must emit
        exactly one ``ERROR setup:`` line, exit 1, and write no log record."""
        import re

        qg = _gate_env(monkeypatch, tmp_path)
        monkeypatch.setattr(qg, "SRC_DIR", tmp_path / "no_src")
        monkeypatch.setattr(qg, "TESTS_DIR", tmp_path / "no_tests")
        exit_code = _run_gate(qg, monkeypatch, [], _fake_run_factory())
        captured = capsys.readouterr()
        assert exit_code == 1
        assert len(re.findall(r"^ERROR setup: ", captured.err, re.MULTILINE)) == 1
        assert not (tmp_path / "metrics" / "gate_log.jsonl").exists()

    def test_fast_run_is_marked_and_never_a_clean_pass(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """AC8: --fast prints the not-a-commit-gate notice, skips coverage,
        logs fast: true, and lands on pass_with_skips — never a clean pass."""
        qg = _gate_env(monkeypatch, tmp_path)
        calls: list = []
        exit_code = _run_gate(qg, monkeypatch, ["--fast"], _fake_run_factory(record=calls))
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "NOT a commit gate" in captured.out
        record = _read_log(tmp_path)
        assert record["fast"] is True
        assert record["checks"]["coverage"] == "skipped"
        assert record["overall"] == "pass_with_skips"
        # The pytest invocation samples explicit files, not the whole tests dir.
        pytest_calls = [c for c in calls if "pytest" in c]
        assert pytest_calls, "expected a sampled pytest invocation"
        assert not any(str(qg.TESTS_DIR) == arg for arg in pytest_calls[0])


# ---------------------------------------------------------------------------
# Regression-ledger guard verification (2026-08-07)
# ---------------------------------------------------------------------------


_LEDGER_HEADER = (
    "| File | Bug Description | Root Cause Class | Fix Date | Test File | Test Function |\n"
    "|------|---|---|---|---|---|\n"
)


def _ledger_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    rows: list[tuple[str, str]],
    test_files: dict[str, str],
):
    """Build a self-contained scratch project for check_regression_ledger.

    ``rows`` is a list of (test_file, test_function) cells; ``test_files`` maps
    a filename under tests/ to its source. Everything lives under tmp_path —
    no repo file is read or written.
    """
    import quality_gate as qg

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(exist_ok=True)
    for name, body in test_files.items():
        (tests_dir / name).write_text(body, encoding="utf-8")

    ledger = tmp_path / "regression-ledger.md"
    ledger.write_text(
        _LEDGER_HEADER
        + "".join(
            f"| src/thing.py | bug | Guard Inversion | 2026-01-01 | {tf} | {fn} |\n"
            for tf, fn in rows
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(qg, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(qg, "REGRESSION_LEDGER", ledger)
    monkeypatch.setattr(qg, "TESTS_DIR", tests_dir)
    return qg


class TestParseGuardNames:
    """The ledger's 'Test Function' cell is prose as often as it is a list."""

    @pytest.mark.parametrize(
        "cell,expected",
        [
            ("test_one", ["test_one"]),
            ("test_one; test_two", ["test_one", "test_two"]),
            ("TestKlass::test_method", ["TestKlass", "test_method"]),
            ("test_p[case-1]", ["test_p"]),
            # Parenthetical asides name OTHER files; they must not become guards
            # of THIS entry. Measured on this repo's ledger 2026-08-07: a looser
            # variant (keep parentheticals, drop the identifier filter) produced
            # 19 not-found hits, 18 of them prose fragments (`also`, `in`, bare
            # paths) and exactly 1 a real pytest identifier.
            ("test_one (also test_two in tests/test_other.py)", ["test_one"]),
            ("test_a and test_b", ["test_a", "test_b"]),
            ("", []),
            ("n/a", []),
            ("see the canary contract", []),
            ("test_dup; test_dup", ["test_dup"]),
        ],
    )
    def test_extraction(self, cell: str, expected: list[str]) -> None:
        from quality_gate import _parse_guard_names

        assert _parse_guard_names(cell) == expected


class TestLedgerVerifiesTheFunctionNotJustTheFile:
    """Deleting a named guard FUNCTION must turn the gate red.

    Until 2026-08-07 ``check_regression_ledger`` parsed ``test_function`` into
    the entry dict and never read it — only ``test_file.exists()`` was checked.
    So the ledger's promise ("this bug has a test that stops it coming back")
    was satisfied by a filename: delete the guard, keep the file, stay green.
    """

    _GUARD_PRESENT = "import pytest\n\n\ndef test_guard_holds():\n    assert True\n"
    _GUARD_DELETED = "import pytest\n\n\ndef test_something_else():\n    assert True\n"

    def test_present_guard_passes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        qg = _ledger_env(
            monkeypatch,
            tmp_path,
            rows=[("tests/test_thing.py", "test_guard_holds")],
            test_files={"test_thing.py": self._GUARD_PRESENT},
        )
        assert qg.check_regression_ledger() is True
        assert "Regression ledger (1 guard(s))" in capsys.readouterr().out

    @pytest.mark.regression
    def test_deleted_guard_function_fails_even_though_the_file_remains(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """THE defect. Same ledger, same existing test file, guard removed."""
        qg = _ledger_env(
            monkeypatch,
            tmp_path,
            rows=[("tests/test_thing.py", "test_guard_holds")],
            test_files={"test_thing.py": self._GUARD_DELETED},
        )
        assert (tmp_path / "tests" / "test_thing.py").exists(), "file must still exist"
        assert qg.check_regression_ledger() is False
        captured = capsys.readouterr()
        assert "Undefined guard: test_guard_holds" in captured.out
        assert "ERROR regression:" in captured.err

    @pytest.mark.regression
    def test_rename_and_deletion_produce_the_identical_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """The check cannot tell a deleted guard from a renamed one, so its
        message must not claim to.

        This pins the wording fix, not a behaviour change. The only instance
        this check has ever found in this repo was a RENAME + migration
        (``test_no_slug_or_env_leak_on_no_db_path`` ->
        ``test_main_render_static_missing_db_no_file_no_browser_no_slug``), and
        the text said the protection was absent. It was not: it still runs. Both
        arms below are red — correctly, a ledger row naming nothing real needs a
        human — but they are red for reasons the code cannot separate, so any
        wording that names one of them is wrong half the time.
        """
        deleted = tmp_path / "deleted"
        renamed = tmp_path / "renamed"
        outs: dict[str, str] = {}

        for label, root, files in (
            (
                "deleted",
                deleted,
                {"test_thing.py": "def test_unrelated():\n    assert True\n"},
            ),
            (
                "renamed",
                renamed,
                {
                    "test_thing.py": "def test_unrelated():\n    assert True\n",
                    # Same protection, migrated + renamed, old name only in prose.
                    "test_new_home.py": (
                        "def test_guard_holds_v2() -> None:\n"
                        '    """Migrated from ``test_guard_holds``."""\n'
                        "    assert True\n"
                    ),
                },
            ),
        ):
            root.mkdir()
            qg = _ledger_env(
                monkeypatch,
                root,
                rows=[("tests/test_thing.py", "test_guard_holds")],
                test_files=files,
            )
            assert qg.check_regression_ledger() is False, label
            outs[label] = capsys.readouterr().out

        def _finding(text: str) -> str:
            return next(line.strip() for line in text.splitlines() if "Undefined guard" in line)

        assert _finding(outs["deleted"]) == _finding(outs["renamed"])
        message = _finding(outs["deleted"])
        # Says what was checked...
        assert "no def/class of that name anywhere" in message
        assert "cannot tell which" in message
        # ...and does not assert the conclusion it cannot reach.
        for overclaim in ("protection is absent", "was deleted", "Missing guard"):
            assert overclaim not in message, message

    @pytest.mark.regression
    def test_docstring_mention_is_not_a_definition(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A renamed guard often survives as a docstring reference. A substring
        search would call that a pass — this is the real shape found in this
        repo's own ledger (test_no_slug_or_env_leak_on_no_db_path)."""
        qg = _ledger_env(
            monkeypatch,
            tmp_path,
            rows=[("tests/test_thing.py", "test_guard_holds")],
            test_files={
                "test_thing.py": (
                    "def test_renamed() -> None:\n"
                    '    """Migrated from the retired test ``test_guard_holds``."""\n'
                    "    assert True\n"
                )
            },
        )
        assert qg.check_regression_ledger() is False

    def test_guard_defined_in_another_test_file_warns_but_passes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Stale bookkeeping (right guard, wrong file) is a WARN, not a red:
        the protection still runs, so blocking the build would cost more than
        the defect does."""
        qg = _ledger_env(
            monkeypatch,
            tmp_path,
            rows=[("tests/test_thing.py", "test_guard_holds")],
            test_files={
                "test_thing.py": "def test_unrelated():\n    assert True\n",
                "test_elsewhere.py": self._GUARD_PRESENT,
            },
        )
        assert qg.check_regression_ledger() is True
        captured = capsys.readouterr()
        assert "actually in" in captured.out
        assert "WARN regression:" in captured.err

    def test_class_guard_is_recognised(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        qg = _ledger_env(
            monkeypatch,
            tmp_path,
            rows=[("tests/test_thing.py", "TestGuardClass::test_case")],
            test_files={
                "test_thing.py": (
                    "class TestGuardClass:\n    def test_case(self):\n        assert True\n"
                )
            },
        )
        assert qg.check_regression_ledger() is True

    def test_missing_test_file_still_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """The original contract is preserved, not replaced."""
        qg = _ledger_env(
            monkeypatch,
            tmp_path,
            rows=[("tests/test_absent.py", "test_guard_holds")],
            test_files={},
        )
        assert qg.check_regression_ledger() is False
        assert "Missing test file" in capsys.readouterr().out

    def test_empty_ledger_passes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        qg = _ledger_env(monkeypatch, tmp_path, rows=[], test_files={})
        assert qg.check_regression_ledger() is True
