#!/bin/bash
# PostToolUse hook: auto-format Python files after Edit/Write
# Receives JSON on stdin with tool call details

set -uo pipefail

# Read the input JSON
INPUT=$(cat)

# Extract the file path from the tool input, with basic path validation
FILE_PATH=$(echo "$INPUT" | python -c "
import json, sys, re
data = json.load(sys.stdin)
tool_input = data.get('tool_input', {})
path = tool_input.get('file_path', '')
if path and re.match(r'^[\w\-./\\\\: ]+$', path):
    print(path)
else:
    print('')
" 2>/dev/null)

# Only format Python files
if [[ -n "$FILE_PATH" && "$FILE_PATH" == *.py ]]; then
    ruff format "$FILE_PATH" 2>/dev/null
    ruff check --fix "$FILE_PATH" 2>/dev/null
fi
