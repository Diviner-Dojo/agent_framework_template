"""Tests for scripts/notify.py — push notification utility."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest

# Add scripts to path for import
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestSendNotification:
    """Tests for the send_notification function."""

    def setup_method(self) -> None:
        """Clear NTFY env vars before each test."""
        for key in ("NTFY_TOPIC", "NTFY_SERVER", "NTFY_TOKEN"):
            os.environ.pop(key, None)

    def teardown_method(self) -> None:
        """Restore clean env after each test."""
        for key in ("NTFY_TOPIC", "NTFY_SERVER", "NTFY_TOKEN"):
            os.environ.pop(key, None)

    @patch.dict(os.environ, {}, clear=True)
    def test_no_topic_returns_false(self) -> None:
        """send_notification returns False when no topic is configured.

        Defensive: explicitly pop NTFY_TOPIC here. The @patch.dict decorator
        should be enough, but in practice notify._load_env() (run at module
        import time) can populate os.environ with NTFY_TOPIC from .env
        depending on test ordering and cached-module state — pop is robust
        against every pollution mode.
        """
        from notify import send_notification

        os.environ.pop("NTFY_TOPIC", None)
        result = send_notification("test message")
        assert result is False

    @patch("notify.urlopen")
    def test_http_200_returns_true(self, mock_urlopen: MagicMock) -> None:
        """send_notification returns True on successful HTTP 200."""
        from notify import send_notification

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = send_notification("test", topic="test-topic")
        assert result is True

    @patch("notify.urlopen")
    def test_non_200_returns_false(self, mock_urlopen: MagicMock) -> None:
        """send_notification returns False on non-200 HTTP status."""
        from notify import send_notification

        mock_resp = MagicMock()
        mock_resp.status = 503
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = send_notification("test", topic="test-topic")
        assert result is False

    @patch("notify.urlopen")
    def test_url_error_returns_false(self, mock_urlopen: MagicMock) -> None:
        """send_notification returns False on URLError (network failure)."""
        from notify import send_notification

        mock_urlopen.side_effect = URLError("Connection refused")

        result = send_notification("test", topic="test-topic")
        assert result is False

    @patch("notify.urlopen")
    def test_unexpected_exception_returns_false(self, mock_urlopen: MagicMock) -> None:
        """send_notification returns False on unexpected exceptions."""
        from notify import send_notification

        mock_urlopen.side_effect = RuntimeError("unexpected")

        result = send_notification("test", topic="test-topic")
        assert result is False

    @patch("notify.urlopen")
    def test_auth_header_set_when_token_provided(self, mock_urlopen: MagicMock) -> None:
        """Authorization header is set when token is provided."""
        from notify import send_notification

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        send_notification("test", topic="test-topic", token="my-token")

        req = mock_urlopen.call_args[0][0]
        assert req.get_header("Authorization") == "Bearer my-token"

    @patch("notify.urlopen")
    def test_title_and_tags_headers_set(self, mock_urlopen: MagicMock) -> None:
        """Title and Tags headers are set when provided."""
        from notify import send_notification

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        send_notification("test", topic="test-topic", title="My Title", tags="rocket,fire")

        req = mock_urlopen.call_args[0][0]
        assert req.get_header("Title") == "My Title"
        assert req.get_header("Tags") == "rocket,fire"

    @patch("notify.urlopen")
    def test_priority_header_not_set_for_default(self, mock_urlopen: MagicMock) -> None:
        """Priority header is not set when priority is 'default'."""
        from notify import send_notification

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        send_notification("test", topic="test-topic", priority="default")

        req = mock_urlopen.call_args[0][0]
        assert not req.has_header("Priority")

    @patch("notify.urlopen")
    def test_custom_server_used_in_url(self, mock_urlopen: MagicMock) -> None:
        """Custom server URL is used when provided."""
        from notify import send_notification

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        send_notification("test", topic="my-topic", server="https://my-ntfy.example.com")

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "https://my-ntfy.example.com/my-topic"

    @patch("notify.urlopen")
    def test_message_encoded_as_utf8_body(self, mock_urlopen: MagicMock) -> None:
        """Message is sent as UTF-8 encoded body."""
        from notify import send_notification

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        send_notification("Hello world!", topic="test-topic")

        req = mock_urlopen.call_args[0][0]
        assert req.data == b"Hello world!"


class TestValidators:
    """Tests for the validate_topic and validate_server helpers."""

    def test_accepts_valid_topic(self) -> None:
        from notify import validate_topic

        assert validate_topic("topic-x") is None
        assert validate_topic("my_topic_42") is None
        assert validate_topic("a") is None
        assert validate_topic("A" * 64) is None

    def test_rejects_empty_topic(self) -> None:
        from notify import validate_topic

        err = validate_topic("")
        assert err is not None
        assert "empty" in err

    def test_rejects_topic_with_special_chars(self) -> None:
        """Topic must reject path traversal, URL-escape, host-injection."""
        from notify import validate_topic

        for bad in [
            "topic@evil.com",
            "../admin",
            "topic?x=1",
            "topic/path",
            "topic with spaces",
            "topic%2F",
            "topic#frag",
        ]:
            err = validate_topic(bad)
            assert err is not None, f"expected rejection for {bad!r}"

    def test_rejects_topic_over_64_chars(self) -> None:
        from notify import validate_topic

        err = validate_topic("A" * 65)
        assert err is not None

    def test_accepts_valid_server(self) -> None:
        from notify import validate_server

        assert validate_server("https://ntfy.sh") is None
        assert validate_server("http://localhost:8080") is None
        assert validate_server("https://my-ntfy.example.com/path") is None

    def test_rejects_empty_server(self) -> None:
        from notify import validate_server

        err = validate_server("")
        assert err is not None

    def test_rejects_non_http_schemes(self) -> None:
        from notify import validate_server

        for bad in ["javascript:alert(1)", "file:///etc/passwd", "data:text/plain,x", "ntfy.sh"]:
            err = validate_server(bad)
            assert err is not None, f"expected rejection for {bad!r}"

    @patch("notify.urlopen")
    def test_send_notification_refuses_invalid_topic(self, mock_urlopen: MagicMock) -> None:
        """send_notification must not POST when topic is invalid."""
        from notify import send_notification

        result = send_notification("test", topic="bad/topic")
        assert result is False
        mock_urlopen.assert_not_called()

    @patch("notify.urlopen")
    def test_send_notification_refuses_invalid_server(self, mock_urlopen: MagicMock) -> None:
        """send_notification must not POST when server has an unsafe scheme."""
        from notify import send_notification

        result = send_notification("test", topic="ok-topic", server="javascript:alert(1)")
        assert result is False
        mock_urlopen.assert_not_called()


class TestLoadEnv:
    """Tests for the _load_env helper."""

    def test_does_not_override_existing_env_var(self, tmp_path: Path) -> None:
        """_load_env does not override already-set environment variables."""
        from notify import _load_env

        env_file = tmp_path / ".env"
        env_file.write_text("NTFY_TOPIC=from-file\n")

        os.environ["NTFY_TOPIC"] = "from-env"

        with patch("notify._ENV_FILE", env_file):
            _load_env()

        assert os.environ["NTFY_TOPIC"] == "from-env"
        os.environ.pop("NTFY_TOPIC", None)

    def test_loads_value_from_env_file(self, tmp_path: Path) -> None:
        """_load_env loads values from .env file when not in environment."""
        from notify import _load_env

        env_file = tmp_path / ".env"
        env_file.write_text("TEST_NOTIFY_VAR=hello\n")

        os.environ.pop("TEST_NOTIFY_VAR", None)

        with patch("notify._ENV_FILE", env_file):
            _load_env()

        assert os.environ.get("TEST_NOTIFY_VAR") == "hello"
        os.environ.pop("TEST_NOTIFY_VAR", None)

    def test_skips_comments_and_blank_lines(self, tmp_path: Path) -> None:
        """_load_env skips comment and blank lines."""
        from notify import _load_env

        env_file = tmp_path / ".env"
        env_file.write_text("# comment\n\nTEST_NOTIFY_VAR2=value\n")

        os.environ.pop("TEST_NOTIFY_VAR2", None)

        with patch("notify._ENV_FILE", env_file):
            _load_env()

        assert os.environ.get("TEST_NOTIFY_VAR2") == "value"
        os.environ.pop("TEST_NOTIFY_VAR2", None)

    def test_strips_quotes_from_values(self, tmp_path: Path) -> None:
        """_load_env strips surrounding quotes from values."""
        from notify import _load_env

        env_file = tmp_path / ".env"
        env_file.write_text('TEST_NOTIFY_VAR3="quoted_value"\n')

        os.environ.pop("TEST_NOTIFY_VAR3", None)

        with patch("notify._ENV_FILE", env_file):
            _load_env()

        assert os.environ.get("TEST_NOTIFY_VAR3") == "quoted_value"
        os.environ.pop("TEST_NOTIFY_VAR3", None)

    def test_handles_value_with_equals_sign(self, tmp_path: Path) -> None:
        """_load_env handles values containing equals signs."""
        from notify import _load_env

        env_file = tmp_path / ".env"
        env_file.write_text("TEST_NOTIFY_VAR4=abc=def=ghi\n")

        os.environ.pop("TEST_NOTIFY_VAR4", None)

        with patch("notify._ENV_FILE", env_file):
            _load_env()

        assert os.environ.get("TEST_NOTIFY_VAR4") == "abc=def=ghi"
        os.environ.pop("TEST_NOTIFY_VAR4", None)

    def test_nonexistent_env_file_is_noop(self, tmp_path: Path) -> None:
        """_load_env is a no-op when .env file does not exist."""
        from notify import _load_env

        fake_path = tmp_path / "nonexistent" / ".env"

        with patch("notify._ENV_FILE", fake_path):
            _load_env()  # Should not raise


class TestEnsureAsciiTitle:
    """Tests for the ensure_ascii_title guard (Protocol 7 / ADR-0019)."""

    def test_ascii_title_unchanged(self) -> None:
        from notify import ensure_ascii_title

        assert ensure_ascii_title("Build complete") == "Build complete"

    def test_emoji_replaced_with_ascii(self) -> None:
        from notify import ensure_ascii_title

        result = ensure_ascii_title("✅ done")
        result.encode("ascii")  # must not raise
        assert "✅" not in result

    @pytest.mark.regression
    @patch("notify.urlopen")
    def test_emoji_title_header_is_latin1_safe(self, mock_urlopen: MagicMock) -> None:
        """Regression: a non-ASCII Title would raise UnicodeEncodeError when urllib
        encodes the HTTP header as latin-1 (same class as src/context_sensor.py,
        2026-05-23). The Title header must be latin-1-encodable after sanitizing.
        """
        from notify import send_notification

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        send_notification("body", title="✅ deploy done", topic="test-topic")

        req = mock_urlopen.call_args[0][0]
        title_header = req.get_header("Title")
        title_header.encode("latin-1")  # the regression assertion: must not raise
        assert "✅" not in title_header


class TestSendNotificationBindShape:
    """ADR-0028 (2a): lock send_notification's BODY-FIRST signature + its caller shape.

    VerificationPortal flipped notify.py to title-first and broke its own callers (B1). The
    hub stays body-first; these tests fail loudly if a future change reorders the parameters
    or makes a caller pass the message by an incompatible binding -- catching the VP-style
    divergence at test time instead of in production.
    """

    @pytest.mark.regression
    def test_send_notification_is_body_first_message_positional(self) -> None:
        """`message` is the first positional parameter; `title` is keyword-only."""
        import inspect

        from notify import send_notification

        params = list(inspect.signature(send_notification).parameters.values())
        # message is the FIRST parameter and bindable positionally (not keyword-only)
        assert params[0].name == "message"
        assert params[0].kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
        # title exists and is keyword-only (so a title-first positional call cannot bind it)
        title = inspect.signature(send_notification).parameters["title"]
        assert title.kind is inspect.Parameter.KEYWORD_ONLY

    @pytest.mark.regression
    def test_send_notification_rejects_title_first_positional(self) -> None:
        """A title-first positional call (VP's B1 shape) must NOT bind silently.

        Binding two positionals against the body-first signature would assign the 2nd to
        `message`-then-error (only `message` is positional), so the VP-style
        ``send_notification(title, body)`` two-positional call is a TypeError here.
        """
        import inspect

        from notify import send_notification

        sig = inspect.signature(send_notification)
        with pytest.raises(TypeError):
            sig.bind("a-title", "a-body")  # two positionals -> no valid bind (body-first)

    @pytest.mark.regression
    def test_collab_loop_say_calls_send_notification_body_first(self) -> None:
        """The collab_loop.say caller passes the body positionally and title by keyword.

        Locks the caller shape so a body-first/title-first mismatch between notify.py and
        its callers (VP's B1 root cause) is caught.
        """
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from unittest.mock import patch as _patch

        with _patch("scripts.collab_loop.send_notification", return_value=True) as mock_send:
            from scripts.collab_loop import say

            assert say("My Title", "the body text") is True
        # body is the first POSITIONAL arg; title rides as a keyword (body-first contract)
        args, kwargs = mock_send.call_args
        assert args[0] == "the body text"
        assert kwargs.get("title") == "My Title"
