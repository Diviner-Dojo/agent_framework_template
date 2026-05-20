"""Ask the developer a question via ntfy and read the reply.

Two usage patterns:

1. Blocking — single call, waits for reply or timeout:
        from scripts.ask_developer import ask
        answer = ask("Should I use SQLite or Postgres?", timeout=300)
        if answer is None:
            print("No reply within timeout")
        else:
            print(f"Developer said: {answer}")

2. Non-blocking — for ScheduleWakeup or /loop workflows. Send once, poll on
   each wakeup until a reply arrives:
        from scripts.ask_developer import send_question, fetch_reply
        ts = send_question("Approve the migration?")
        # ... ScheduleWakeup(delaySeconds=300) ...
        # On wake:
        reply = fetch_reply(ts)
        if reply is None:
            # not yet — schedule another wake
            ...

Filtering: outbound questions carry title "Claude needs input". fetch_reply
skips messages with that title (echo guard), so any free-text reply you send
from the ntfy app on the same topic is treated as the answer.

Configuration: requires NTFY_TOPIC in .env (same as scripts/notify.py).

Note on confidentiality: the question body is published to ntfy.sh. Keep
question text generic — the topic slug is the only access control. See
.claude/skills/notifying-the-developer/SKILL.md for the full protocol.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

# Ensure project root is on sys.path so `python scripts/ask_developer.py` works
# in addition to `python -m scripts.ask_developer`.
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.notify import send_notification, validate_server, validate_topic  # noqa: E402

logger = logging.getLogger(__name__)

QUESTION_TITLE = "Claude needs input"
QUESTION_TAG = "question"
DEFAULT_SERVER = "https://ntfy.sh"
DEFAULT_TIMEOUT = 3600  # 1 hour — see .claude/skills/notifying-the-developer/SKILL.md
DEFAULT_POLL_INTERVAL = 5
POLL_HTTP_TIMEOUT = 15


def _topic_and_server() -> tuple[str, str]:
    """Resolve and validate topic + server from environment.

    Raises RuntimeError if NTFY_TOPIC is missing or fails validation, or if
    NTFY_SERVER fails validation. Validation rejects topics with path-traversal,
    URL-escape, or host-injection characters, and servers without an http(s)
    scheme — preventing the env-controlled URL from escaping the intended host.
    """
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    server = os.environ.get("NTFY_SERVER", DEFAULT_SERVER).rstrip("/")
    if not topic:
        raise RuntimeError("NTFY_TOPIC not set (check .env)")
    topic_err = validate_topic(topic)
    if topic_err:
        raise RuntimeError(f"NTFY_TOPIC invalid: {topic_err}")
    server_err = validate_server(server)
    if server_err:
        raise RuntimeError(f"NTFY_SERVER invalid: {server_err}")
    return topic, server


def send_question(
    question: str,
    *,
    title: str = QUESTION_TITLE,
    priority: str = "high",
) -> int:
    """Publish a question to ntfy. Returns the unix timestamp marking the send.

    Use the returned timestamp with fetch_reply() to poll for an answer.
    Raises RuntimeError if the publish fails.
    """
    sent_at = int(time.time())
    ok = send_notification(
        question,
        title=title,
        priority=priority,
        tags=QUESTION_TAG,
    )
    if not ok:
        raise RuntimeError("Failed to publish question via ntfy (check NTFY_TOPIC)")
    return sent_at


def fetch_reply(
    since: int,
    *,
    question_title: str = QUESTION_TITLE,
) -> str | None:
    """Poll ntfy once for a reply posted after `since` (unix timestamp).

    Returns the first reply body that is NOT an echo of our outbound question
    (filtered by title). Returns None if no qualifying message is available.
    Network errors are swallowed and treated as "no reply yet".
    """
    topic, server = _topic_and_server()
    url = f"{server}/{topic}/json?poll=1&since={since}"
    try:
        with urlopen(url, timeout=POLL_HTTP_TIMEOUT) as resp:
            for raw in resp:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if msg.get("event") != "message":
                    continue
                if msg.get("title") == question_title:
                    continue
                body = msg.get("message", "").strip()
                if body:
                    return body
    except URLError as e:
        logger.debug("ntfy poll failed (treating as no reply): %s", e)
        return None
    return None


def ask(
    question: str,
    *,
    title: str = QUESTION_TITLE,
    timeout: int = DEFAULT_TIMEOUT,
    poll_interval: int = DEFAULT_POLL_INTERVAL,
    priority: str = "high",
    sleep: object = time.sleep,
) -> str | None:
    """Send a question via ntfy and block until a reply arrives or timeout.

    Args:
        question: The question to send.
        title: Notification title (also the echo-filter key).
        timeout: Max seconds to wait for a reply. Default 3600 (1 hour).
        poll_interval: Seconds between polls. Default 5.
        priority: ntfy priority. Default "high".
        sleep: Sleep function (injected for testing).

    Returns:
        The reply body, or None if no reply within `timeout`.
    """
    sent_at = send_question(question, title=title, priority=priority)
    deadline = sent_at + timeout
    while time.time() < deadline:
        reply = fetch_reply(sent_at, question_title=title)
        if reply is not None:
            return reply
        sleep(poll_interval)  # type: ignore[operator]
    return None


def main() -> None:
    """CLI entry point — blocking ask() with shell-friendly output."""
    parser = argparse.ArgumentParser(
        description="Ask the developer a question via ntfy and wait for a reply",
    )
    parser.add_argument("question", help="The question to send")
    parser.add_argument("--title", default=QUESTION_TITLE)
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Max seconds to wait (default {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=DEFAULT_POLL_INTERVAL,
        help=f"Seconds between polls (default {DEFAULT_POLL_INTERVAL})",
    )
    parser.add_argument(
        "--priority",
        default="high",
        choices=["min", "low", "default", "high", "max"],
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    reply = ask(
        args.question,
        title=args.title,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
        priority=args.priority,
    )
    if reply is None:
        print("No reply within timeout.", file=sys.stderr)
        raise SystemExit(2)
    print(reply, flush=True)


if __name__ == "__main__":
    main()
