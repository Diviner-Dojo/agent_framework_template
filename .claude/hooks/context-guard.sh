#!/bin/bash
# UserPromptSubmit: inject a wrap-up nudge when context crosses a model-specific
# threshold (ADR-0018). Delegates to Python -> src/context_sensor.py. Advisory
# only (v1); never blocks the turn.
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cat | python "$HOOK_DIR/context_guard.py"