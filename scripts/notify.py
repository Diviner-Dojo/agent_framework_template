"""Push notification utility using ntfy.sh.

Sends push notifications to developer's phone/desktop when long-running
tasks complete. Uses ntfy.sh (https://ntfy.sh) — no account required,
just a topic slug.

Configuration via environment variables (in .env):
    NTFY_TOPIC    — Required. Your unique topic slug (treat like a key).
    NTFY_SERVER   — Optional. Custom ntfy server URL (default: https://ntfy.sh).
    NTFY_TOKEN    — Optional. Bearer token for authenticated servers.

Usage:
    # As a script:
    python scripts/notify.py "Build complete" --title "MyProject"
    python scripts/notify.py "Tests passed" --priority high --tags white_check_mark

    # As a library:
    from scripts.notify import send_notification
    send_notification("Build complete", title="MyProject")

All notifications are best-effort — failures never block the calling script.
Uses stdlib only (urllib) — no pip dependencies.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

# Load .env if python-dotenv is not available — manual parse
_ENV_FILE = Path(__file__).parent.parent / ".env"


def _load_env() -> None:
    """Load variables from .env file if it exists.

    Simple parser — handles KEY=VALUE and KEY="VALUE" lines.
    Does not override existing environment variables.
    """
    if not _ENV_FILE.exists():
        return
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env()

DEFAULT_SERVER = "https://ntfy.sh"


def send_notification(
    message: str,
    *,
    title: str | None = None,
    priority: str = "default",
    tags: str | None = None,
    topic: str | None = None,
    server: str | None = None,
    token: str | None = None,
) -> bool:
    """Send a push notification via ntfy.sh.

    Args:
        message: Notification body text.
        title: Optional notification title.
        priority: Priority level (min, low, default, high, max).
        tags: Comma-separated emoji shortcodes (e.g. "white_check_mark,rocket").
        topic: Override NTFY_TOPIC env var.
        server: Override NTFY_SERVER env var.
        token: Override NTFY_TOKEN env var.

    Returns:
        True if notification was sent successfully, False otherwise.
        Never raises — all errors are logged and swallowed.
    """
    topic = topic or os.environ.get("NTFY_TOPIC", "")
    server = server or os.environ.get("NTFY_SERVER", DEFAULT_SERVER)
    token = token or os.environ.get("NTFY_TOKEN", "")

    if not topic:
        logger.debug("NTFY_TOPIC not set — skipping notification")
        return False

    url = f"{server.rstrip('/')}/{topic}"

    headers: dict[str, str] = {}
    if title:
        headers["Title"] = title
    if priority and priority != "default":
        headers["Priority"] = priority
    if tags:
        headers["Tags"] = tags
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        req = Request(
            url,
            data=message.encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                logger.debug("Notification sent: %s", message[:50])
                return True
            else:
                logger.warning("ntfy returned status %d", resp.status)
                return False
    except URLError as e:
        logger.debug("ntfy send failed (best-effort): %s", e)
        return False
    except Exception as e:
        logger.debug("ntfy unexpected error (best-effort): %s", e)
        return False


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Send a push notification via ntfy.sh")
    parser.add_argument("message", help="Notification body text")
    parser.add_argument("--title", "-t", help="Notification title")
    parser.add_argument(
        "--priority",
        "-p",
        default="default",
        choices=["min", "low", "default", "high", "max"],
        help="Notification priority (default: default)",
    )
    parser.add_argument("--tags", help="Comma-separated emoji shortcodes (e.g. white_check_mark)")
    parser.add_argument("--topic", help="Override NTFY_TOPIC env var")
    parser.add_argument("--server", help="Override NTFY_SERVER env var")
    parser.add_argument("--token", help="Override NTFY_TOKEN env var")

    args = parser.parse_args()

    # Enable logging for CLI usage
    logging.basicConfig(level=logging.DEBUG)

    success = send_notification(
        args.message,
        title=args.title,
        priority=args.priority,
        tags=args.tags,
        topic=args.topic,
        server=args.server,
        token=args.token,
    )

    if success:
        print("Notification sent.")
    else:
        print("Notification not sent (check NTFY_TOPIC in .env).", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
