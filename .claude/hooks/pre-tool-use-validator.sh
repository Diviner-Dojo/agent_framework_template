#!/bin/bash
# PreToolUse hook: File locking + protected files + secret detection
# Delegates to Python for robust path handling on Windows
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cat | python "$HOOK_DIR/validate_tool_use.py"
