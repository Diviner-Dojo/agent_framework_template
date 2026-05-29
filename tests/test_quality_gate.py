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

    def test_record_has_stable_schema_keys(self) -> None:
        """The record exposes the documented top-level keys for trend queries."""
        from quality_gate import _build_outcome_record

        record = _build_outcome_record(_make_args(), [True] * 7, passed=7, total=7)

        assert set(record) == {
            "timestamp",
            "overall",
            "passed_count",
            "total",
            "skipped_count",
            "checks",
        }


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
