"""Tests for scripts/notify.py — push notification utility."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import URLError

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
