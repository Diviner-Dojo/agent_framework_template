#!/usr/bin/env python3
"""Queue a one-shot notification to fire on the next Stop-hook execution.

Writes ``.claude/hooks/.state/next-stop-notify.json``. The Stop hook
(``scripts/stop_hook.py``) reads it on the next turn end, fires exactly one
ntfy notification with the supplied title/body, optionally polls for an
allow-listed reply, and deletes the file.

Use this when you reach a natural pause point and the developer should be
informed of what just happened AND what to do next. The body should answer
both: "what state are we in?" and "what's the next action?"

Origin: back-flow pattern ``one-shot-stop-hook`` from dan_research_karpathy_wiki
(wiki source: tools/queue-stop-notify.py).

Examples::

    # Quick "done, here's what's next" handoff (no wait):
    python scripts/queue_stop_notify.py \
      --title "Run 2 complete" \
      --body "D2 patterns committed on feat/d2-backflow-patterns. Next: developer merge." \
      --tags white_check_mark

    # Pause for a gated decision with a reply window:
    python scripts/queue_stop_notify.py \
      --title "Decision needed" \
      --body "ASSESS found 2 conflicts. Reply 'Retry' to re-run, 'Park' to skip." \
      --priority high --tags question --wait --wait-timeout 600 \
      --choices Retry Park

Replies are untrusted out-of-band input (CLAUDE.md Always-On Invariant):
``--wait`` therefore REQUIRES ``--choices``; the Stop hook acts only on a
reply matching that allow-list and injects only the matched label as the next
prompt (``decision: block`` contract). A non-matching reply triggers nothing.

The state file is gitignored (per-machine), single-purpose, one-shot.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
STATE_FILE = PROJECT_ROOT / ".claude" / "hooks" / ".state" / "next-stop-notify.json"
WAIT_TIMEOUT_CAP = 600  # keep in sync with scripts/stop_hook.py


def build_intent(args: argparse.Namespace) -> dict:
    """Build the intent payload from parsed CLI args."""
    return {
        "title": args.title,
        "body": args.body,
        "priority": args.priority,
        "tags": args.tags,
        "wait_for_reply": args.wait,
        "wait_timeout_seconds": min(args.wait_timeout, WAIT_TIMEOUT_CAP),
        "choices": args.choices or [],
        # The hook discards intents older than its TTL, so a forgotten
        # STOP_HOOK_DISABLE=1 can't fire a stale gated question later.
        "queued_at": int(time.time()),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--title", required=True, help="Short notification title")
    p.add_argument("--body", default="", help="Body -- say what happened AND what's next")
    p.add_argument(
        "--priority",
        default="default",
        # Must stay aligned with scripts/notify.py's documented set.
        choices=["min", "low", "default", "high", "max"],
    )
    p.add_argument("--tags", default="", help="Comma-separated emoji shortcodes")
    p.add_argument(
        "--wait",
        action="store_true",
        help="Poll ntfy for an allow-listed reply after firing (requires --choices)",
    )
    p.add_argument(
        "--wait-timeout",
        type=int,
        default=120,
        help=f"Seconds to poll if --wait (default 120, capped at {WAIT_TIMEOUT_CAP})",
    )
    p.add_argument(
        "--choices",
        nargs="+",
        default=None,
        help="Allow-listed reply labels; the hook acts ONLY on a matching reply",
    )
    args = p.parse_args(argv)

    if args.wait and not args.choices:
        p.error("--wait requires --choices (out-of-band replies are allow-list-only)")

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(build_intent(args), indent=2), encoding="utf-8")
    # ASCII-safe confirmation: cp1252 terminals crash on non-ASCII prints
    # (recurring regression class, see memory/bugs/regression-ledger.md).
    safe_title = args.title.encode("ascii", "replace").decode("ascii")
    print(f"Queued stop notification: {safe_title}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
