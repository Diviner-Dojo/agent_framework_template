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
