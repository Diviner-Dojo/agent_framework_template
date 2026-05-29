#!/usr/bin/env python3
"""UserPromptSubmit hook wrapper (ADR-0018).

Thin: read the hook JSON on stdin, delegate to ``src.context_sensor.evaluate_guard``
to decide whether a wrap-up nudge is due, and emit it as ``additionalContext``. All
real logic lives in the coverage-measured core; this wrapper only does I/O and must
never raise (a guard failure must not block the turn).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.context_sensor import evaluate_guard  # noqa: E402


def main() -> None:
    """Read stdin JSON, evaluate the guard, print any additionalContext."""
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    try:
        result = evaluate_guard(payload)
    except Exception:  # the guard must never block the turn — degrade to silence.
        result = {}
    additional = result.get("additionalContext")
    if additional:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "UserPromptSubmit",
                        "additionalContext": additional,
                    }
                }
            )
        )


if __name__ == "__main__":
    main()
