"""Tests for scripts/ask_developer.py."""

from __future__ import annotations

import io
import json
from collections.abc import Iterator
from unittest.mock import patch

import pytest

from scripts import ask_developer


def _msg(event: str, *, title: str | None = None, message: str = "") -> bytes:
    """Build a single ntfy-style NDJSON line."""
    payload: dict[str, object] = {"event": event}
    if title is not None:
        payload["title"] = title
    if message:
        payload["message"] = message
    return (json.dumps(payload) + "\n").encode("utf-8")


def _fake_response(lines: list[bytes]) -> object:
    """Build a context-manager mock matching urlopen's interface."""

    class _CM:
        def __enter__(self) -> Iterator[bytes]:
            return iter(lines)

        def __exit__(self, *args: object) -> None:
            return None

    return _CM()


class TestTopicAndServer:
    def test_raises_when_topic_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NTFY_TOPIC", raising=False)
        with pytest.raises(RuntimeError, match="NTFY_TOPIC not set"):
            ask_developer._topic_and_server()

    def test_uses_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NTFY_TOPIC", "topic-x")
        monkeypatch.delenv("NTFY_SERVER", raising=False)
        topic, server = ask_developer._topic_and_server()
        assert topic == "topic-x"
        assert server == "https://ntfy.sh"

    def test_custom_server_trims_trailing_slash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NTFY_TOPIC", "topic-x")
        monkeypatch.setenv("NTFY_SERVER", "https://ntfy.example.com/")
        _, server = ask_developer._topic_and_server()
        assert server == "https://ntfy.example.com"

    def test_rejects_topic_with_path_traversal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NTFY_TOPIC", "../admin")
        with pytest.raises(RuntimeError, match="NTFY_TOPIC invalid"):
            ask_developer._topic_and_server()

    def test_rejects_topic_with_host_injection(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NTFY_TOPIC", "topic@evil.com")
        with pytest.raises(RuntimeError, match="NTFY_TOPIC invalid"):
            ask_developer._topic_and_server()

    def test_rejects_topic_with_url_escape(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NTFY_TOPIC", "topic%2Fpath")
        with pytest.raises(RuntimeError, match="NTFY_TOPIC invalid"):
            ask_developer._topic_and_server()

    def test_rejects_server_with_unsafe_scheme(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NTFY_TOPIC", "topic-x")
        monkeypatch.setenv("NTFY_SERVER", "javascript:alert(1)")
        with pytest.raises(RuntimeError, match="NTFY_SERVER invalid"):
            ask_developer._topic_and_server()


class TestSendQuestion:
    def test_returns_timestamp_when_publish_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NTFY_TOPIC", "topic-x")
        with patch.object(ask_developer, "send_notification", return_value=True) as mock_send:
            ts = ask_developer.send_question("hello?")
        assert isinstance(ts, int)
        assert ts > 0
        mock_send.assert_called_once_with(
            "hello?",
            title=ask_developer.QUESTION_TITLE,
            priority="high",
            tags=ask_developer.QUESTION_TAG,
        )

    def test_passes_custom_title_and_priority_through(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NTFY_TOPIC", "topic-x")
        with patch.object(ask_developer, "send_notification", return_value=True) as mock_send:
            ask_developer.send_question("hi", title="Custom Title", priority="max")
        mock_send.assert_called_once_with(
            "hi",
            title="Custom Title",
            priority="max",
            tags=ask_developer.QUESTION_TAG,
        )

    def test_raises_when_publish_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NTFY_TOPIC", "topic-x")
        with patch.object(ask_developer, "send_notification", return_value=False):
            with pytest.raises(RuntimeError, match="Failed to publish"):
                ask_developer.send_question("hello?")


class TestFetchReply:
    def test_returns_first_non_echo_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NTFY_TOPIC", "topic-x")
        lines = [
            _msg("open"),
            _msg("message", title=ask_developer.QUESTION_TITLE, message="our outbound"),
            _msg("message", title="reply from phone", message="use sqlite"),
        ]
        with patch.object(ask_developer, "urlopen", return_value=_fake_response(lines)):
            reply = ask_developer.fetch_reply(since=1000)
        assert reply == "use sqlite"

    def test_returns_none_when_only_echo_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NTFY_TOPIC", "topic-x")
        lines = [
            _msg("message", title=ask_developer.QUESTION_TITLE, message="our outbound"),
        ]
        with patch.object(ask_developer, "urlopen", return_value=_fake_response(lines)):
            reply = ask_developer.fetch_reply(since=1000)
        assert reply is None

    def test_returns_none_when_no_messages(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NTFY_TOPIC", "topic-x")
        with patch.object(ask_developer, "urlopen", return_value=_fake_response([])):
            reply = ask_developer.fetch_reply(since=1000)
        assert reply is None

    def test_skips_malformed_json_lines(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NTFY_TOPIC", "topic-x")
        lines = [
            b"not json at all\n",
            _msg("message", title="reply", message="real reply"),
        ]
        with patch.object(ask_developer, "urlopen", return_value=_fake_response(lines)):
            reply = ask_developer.fetch_reply(since=1000)
        assert reply == "real reply"

    def test_swallows_network_errors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from urllib.error import URLError

        monkeypatch.setenv("NTFY_TOPIC", "topic-x")
        with patch.object(ask_developer, "urlopen", side_effect=URLError("network down")):
            reply = ask_developer.fetch_reply(since=1000)
        assert reply is None

    def test_ignores_non_message_events(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NTFY_TOPIC", "topic-x")
        lines = [
            _msg("open"),
            _msg("keepalive"),
            _msg("message", title="reply", message="picked"),
        ]
        with patch.object(ask_developer, "urlopen", return_value=_fake_response(lines)):
            reply = ask_developer.fetch_reply(since=1000)
        assert reply == "picked"

    def test_skips_empty_message_bodies(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NTFY_TOPIC", "topic-x")
        lines = [
            _msg("message", title="empty", message=""),
            _msg("message", title="reply", message="real"),
        ]
        with patch.object(ask_developer, "urlopen", return_value=_fake_response(lines)):
            reply = ask_developer.fetch_reply(since=1000)
        assert reply == "real"


class TestAsk:
    def test_returns_reply_immediately_when_available(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NTFY_TOPIC", "topic-x")
        with (
            patch.object(ask_developer, "send_notification", return_value=True),
            patch.object(ask_developer, "fetch_reply", return_value="yes"),
        ):
            reply = ask_developer.ask("ready?", timeout=10, poll_interval=1)
        assert reply == "yes"

    def test_polls_until_reply_arrives(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NTFY_TOPIC", "topic-x")
        responses = iter([None, None, "go"])
        sleeps: list[float] = []
        with (
            patch.object(ask_developer, "send_notification", return_value=True),
            patch.object(
                ask_developer,
                "fetch_reply",
                side_effect=lambda *a, **kw: next(responses),
            ),
        ):
            reply = ask_developer.ask(
                "ready?",
                timeout=60,
                poll_interval=1,
                sleep=sleeps.append,
            )
        assert reply == "go"
        assert len(sleeps) == 2

    def test_returns_none_on_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NTFY_TOPIC", "topic-x")
        # Force the deadline to fall before the first poll completes by
        # patching time.time to advance past the deadline on the second call.
        times = iter([1000, 1000, 9999, 9999, 9999])
        with (
            patch.object(ask_developer, "send_notification", return_value=True),
            patch.object(ask_developer, "fetch_reply", return_value=None),
            patch.object(ask_developer.time, "time", side_effect=lambda: next(times)),
        ):
            reply = ask_developer.ask(
                "ready?",
                timeout=10,
                poll_interval=1,
                sleep=lambda _s: None,
            )
        assert reply is None


class TestMainCli:
    def test_main_prints_reply_on_success(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("NTFY_TOPIC", "topic-x")
        monkeypatch.setattr(
            "sys.argv",
            ["ask_developer.py", "go?", "--timeout", "1", "--poll-interval", "1"],
        )
        with patch.object(ask_developer, "ask", return_value="yes"):
            ask_developer.main()
        out = capsys.readouterr().out
        assert "yes" in out

    def test_main_exits_2_on_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NTFY_TOPIC", "topic-x")
        monkeypatch.setattr(
            "sys.argv",
            ["ask_developer.py", "go?", "--timeout", "1", "--poll-interval", "1"],
        )
        with patch.object(ask_developer, "ask", return_value=None):
            with pytest.raises(SystemExit) as exc:
                ask_developer.main()
        assert exc.value.code == 2


# Silence the unused-import warning for io (kept for symmetry with other test files)
_ = io
