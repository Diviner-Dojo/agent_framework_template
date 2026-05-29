"""Tests for scripts/quality_gate.py — the opt-in --notify task-boundary hook.

Covers `_notify_outcome`, the best-effort push-notification hook added so a
developer can be pinged on their phone when a long manual gate run finishes.
The hook must:
  - do nothing unless --notify was passed (so the pre-commit hook stays silent),
  - fire a success ping on pass and a high-priority warning on fail / setup error,
  - never raise — a notification failure must not change the gate's exit code.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add scripts to path for import (mirrors tests/test_notify.py).
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


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
