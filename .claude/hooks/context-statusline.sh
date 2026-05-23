#!/bin/bash
# statusLine: write the context-occupancy sidecar + print a one-line display (ADR-0018).
# Delegates to Python (which delegates to src/context_sensor.py) for robust,
# cross-platform path handling. Must never fail the status line.
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cat | python "$HOOK_DIR/context_statusline.py"