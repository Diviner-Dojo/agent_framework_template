#!/usr/bin/env python3
"""statusLine hook wrapper (ADR-0018).

Thin: read the statusLine JSON on stdin, delegate to ``src.context_sensor`` to
write the occupancy sidecar, and print the one-line display. All real logic lives
in the coverage-measured core; this wrapper only does I/O and must never raise.
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
