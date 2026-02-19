#!/bin/bash
# PostToolUse hook: Release file locks after Write/Edit completes
# Companion to pre-tool-use-validator.sh file locking

set -e

INPUT=$(cat)

# Parse file path and session ID
read -r FILE_PATH SESSION_ID < <(echo "$INPUT" | python -c "
import json, sys
data = json.load(sys.stdin)
tool_input = data.get('tool_input', {})
file_path = tool_input.get('file_path', tool_input.get('path', ''))
session_id = data.get('session_id', '')
print(f'{file_path}\t{session_id}')
" 2>/dev/null || echo "	")

if [[ -z "$FILE_PATH" ]]; then
    exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
LOCK_DIR="$PROJECT_DIR/.claude/hooks/.locks"

# Get relative path
if [[ "$FILE_PATH" == "$PROJECT_DIR"* ]]; then
    REL_PATH="${FILE_PATH#$PROJECT_DIR/}"
else
    REL_PATH="$FILE_PATH"
fi

LOCK_FILE="$LOCK_DIR/$(echo "$REL_PATH" | tr '/' '_' | tr '\\' '_').lock"

# Release lock only if we own it
if [[ -f "$LOCK_FILE" ]]; then
    LOCK_SESSION=$(python -c "
import json
with open('$LOCK_FILE') as f:
    print(json.load(f).get('session_id', ''))
" 2>/dev/null || echo "")

    if [[ "$LOCK_SESSION" == "$SESSION_ID" ]]; then
        rm -f "$LOCK_FILE"
    fi
fi

exit 0
