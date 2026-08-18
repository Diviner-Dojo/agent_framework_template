#!/usr/bin/env python3
"""statusLine hook wrapper (ADR-0018).

Thin: read the statusLine JSON on stdin, delegate to ``src.context_sensor`` to
write the occupancy sidecar, and print the one-line display. All real logic lives
in the coverage-measured core; this wrapper only does I/O and must never raise.

THIS IS THE DEVELOPER-FACING SURFACE, and it KEEPS its numbers. Its stdout is
rendered on the terminal status line for the human, and is never injected into the
model's context. The 2026-08-08 amendment that stripped figures from the
model-facing nudge (see ``context_guard.py``) deliberately did NOT touch this line:
removing the developer's ability to see occupancy was never the goal, and the
resolution markers (``~`` normalized / ``?`` defaulted / ``!`` window mismatch) are
the only place a mis-resolved profile is audible.

Measured 2026-08-08 by piping payloads through this file. The marker is part of the
reading, so the input that produces each one is named rather than implied — an
earlier version of this docstring showed a ``~`` against an input that does not
produce one::

    model=claude-opus-4-7  65.1312% of 1000000
      -> ctx 65% | 651K/1000K | opus_1m | soft 300K hard 400K [wrap-up]
    model=claude-opus-5[1m]  (same reading; resolved by NORMALIZATION)
      -> ctx 65% | 651K/1000K | opus_1m~ | soft 300K hard 400K [wrap-up]
    model=who-knows-9  (unrecognised -> conservative floor, window disagrees)
      -> ctx 65% | 651K/1000K | haiku_200k! | soft 100K hard 130K [wrap-up]

The first two are re-run as assertions by
``TestModelFacingNudgeCarriesNoFigures::test_the_status_line_reproduces_the_readings_the_records_quote``.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.context_sensor import process_statusline  # noqa: E402


def main() -> None:
    """Read stdin JSON, write the sidecar, print the status line."""
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    try:
        line = process_statusline(payload)
    except Exception:  # statusLine must never crash the prompt — degrade to a stub.
        line = "ctx —"
    print(line)


if __name__ == "__main__":
    main()
