#!/bin/bash
# PostToolUse hook: Release file locks after Write/Edit completes
# Delegates to Python for robust path handling on Windows
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cat | python "$HOOK_DIR/release_lock.py"
