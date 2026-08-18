#!/usr/bin/env python3
"""UserPromptSubmit hook wrapper (ADR-0018).

Thin: read the hook JSON on stdin, delegate to ``src.context_sensor.evaluate_guard``
to decide whether a wrap-up nudge is due, and emit it as ``additionalContext``. All
real logic lives in the coverage-measured core; this wrapper only does I/O and must
never raise (a guard failure must not block the turn).

THIS IS THE MODEL-FACING SURFACE. Whatever this prints as ``additionalContext`` is
injected into the model's context on every prompt — measured 2026-08-07/08 by piping
a real payload through this file. That is why the nudge text carries **no figures**:
surfacing a remaining-token count to the model is a documented cause of premature
wrap-up (ADR-0033, amendment 2026-08-08; see ``src.context_sensor._nudge_text``).
Do not add occupancy, percentage, threshold, or window values here or upstream.

The same split has a second, less obvious rule. The injected text is ONE constant
for every profile, so it may only assert what is true at the tightest one. The
first version of this amendment reassured the model that "context remaining is
ample"; measured, a ``sonnet_200k`` session received that with 26000 tokens left
before auto-compaction (1.04x the handoff reserve). Say what the thresholds
guarantee everywhere — room to write the handoff is reserved — not how full the
window is. See ``src.context_sensor._nudge_text``.

The developer-facing surface is the sibling ``context_statusline.py``, which prints
to the terminal status line and DOES carry the numbers. That split is the whole
design: the human keeps the instrument, the model does not get a countdown.
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
