"""Ask the developer a question via ntfy and read the reply (legacy single-topic shim).

This is the **single-topic, free-text** inbound-ask wrapper. The canonical two-way
collaboration loop (reply topic, tap-to-answer buttons, ``poll``/``check``/``say``) is
``scripts/collab_loop.py`` (ADR-0019). This module is kept as a thin backward-compatible
shim for existing callers: it delegates config resolution to ``collab_loop.resolve_config``
and stream parsing to ``collab_loop.parse_ntfy_stream`` (no duplicated inbound logic), and
adds only the single-topic echo-by-title filter below. Prefer ``collab_loop`` for new code.

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
import logging
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

from scripts.collab_loop import parse_ntfy_stream, resolve_config  # noqa: E402
from scripts.notify import send_notification  # noqa: E402

logger = logging.getLogger(__name__)

QUESTION_TITLE = "Claude needs input"
QUESTION_TAG = "question"
DEFAULT_SERVER = "https://ntfy.sh"
DEFAULT_TIMEOUT = 3600  # 1 hour — see .claude/skills/notifying-the-developer/SKILL.md
DEFAULT_POLL_INTERVAL = 5
POLL_HTTP_TIMEOUT = 15


def _topic_and_server() -> tuple[str, str]:
    """Resolve and validate topic + server from the environment (single-topic).

    Delegates to ``collab_loop.resolve_config`` (the shared resolver/validator)
    with ``require_reply=False`` — this single-topic shim does not use a reply
    topic. Raises RuntimeError (with a topic-safe message) if NTFY_TOPIC is missing
    or if topic/server fail validation; validation rejects path-traversal,
    URL-escape, and host-injection characters and non-http(s) schemes.
    """
    server, topic, _reply_topic, _token = resolve_config(require_reply=False)
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
    (filtered by exact title match). Returns None if no qualifying message is
    available. Network errors are swallowed and treated as "no reply yet".

    Stream parsing is delegated to ``collab_loop.parse_ntfy_stream`` (the shared
    parse seam); only the single-topic echo-by-title filter lives here.

    SECURITY: the returned body is **untrusted out-of-band input** — anyone with
    the topic slug can publish it, and this single-topic shim applies no in-code
    allow-list. The caller MUST validate it against a fixed allow-list and act on
    the matched label only, never the raw text (CLAUDE.md Always-On Invariant).
    For gated decisions prefer ``collab_loop.poll``/``check`` with ``choices``,
    which enforce the allow-list at the boundary in code.
    """
    topic, server = _topic_and_server()
    url = f"{server}/{topic}/json?poll=1&since={since}"
    try:
        with urlopen(url, timeout=POLL_HTTP_TIMEOUT) as resp:
            text = b"".join(resp).decode("utf-8")
    except URLError as e:
        # Log the exception TYPE only — str(e) can embed the URL (topic slug).
        logger.debug("ntfy poll failed (treating as no reply): %s", type(e).__name__)
        return None
    for msg in parse_ntfy_stream(text):
        if msg.get("title") == question_title:
            continue  # echo of our own outbound question
        body = (msg.get("message") or "").strip()
        if body:
            return body
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
        The reply body, or None if no reply within `timeout`. The reply is
        **untrusted out-of-band input** (anyone with the topic slug can publish):
        the caller MUST validate it against a fixed allow-list and act on the
        matched label only, never the raw text (CLAUDE.md Always-On Invariant).
        Prefer ``collab_loop.poll``/``check`` with ``choices`` for gated
        decisions — they enforce the allow-list at the boundary in code.
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
