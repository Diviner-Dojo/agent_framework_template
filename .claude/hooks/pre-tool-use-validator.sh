#!/bin/bash
# PreToolUse hook: File locking + secret detection for Write/Edit operations
# Prevents concurrent agent edits and catches secrets before they're written
#
# File Locking:
#   - Atomic lock acquisition via mkdir (race-condition safe)
#   - Locks auto-expire after 120 seconds
#   - Session-based: locks tied to the session that created them
#   - Released on PostToolUse via post-tool-use-unlock.sh
#
# Secret Detection:
#   - Scans content for 6 secret patterns (API keys, AWS keys, JWT, etc.)
#   - Skips test files to reduce false positives
#   - Uses "ask" permission to flag without hard-blocking

set -eo pipefail

INPUT=$(cat)

# Parse tool input using Python (jq may not be available on Windows)
read -r TOOL_NAME FILE_PATH SESSION_ID CONTENT < <(echo "$INPUT" | python -c "
import json, sys
data = json.load(sys.stdin)
tool_name = data.get('tool_name', '')
tool_input = data.get('tool_input', {})
file_path = tool_input.get('file_path', tool_input.get('path', ''))
session_id = data.get('session_id', '')
content = tool_input.get('content', tool_input.get('new_string', ''))
# Replace newlines with spaces for safe shell transport (content checked via Python below)
print(f'{tool_name}\t{file_path}\t{session_id}\t{len(content)}')
" 2>/dev/null || echo "	")

# Exit if not a file operation
if [[ -z "$FILE_PATH" ]]; then
    exit 0
fi

# --- Protected Files ---
# Block edits to critical system files
PROTECTED=false
case "$FILE_PATH" in
    *.git/*) PROTECTED=true ;;
    *.env) PROTECTED=true ;;
    */.env) PROTECTED=true ;;
    */metrics/evaluation.db) PROTECTED=true ;;
esac

if [[ "$PROTECTED" == "true" ]]; then
    cat << 'DENY_EOF'
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "Cannot modify protected file. Use appropriate commands or escalate."}}
DENY_EOF
    exit 0
fi

# --- File Locking ---
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
LOCK_DIR="$PROJECT_DIR/.claude/hooks/.locks"
mkdir -p "$LOCK_DIR"

# Get relative path for lock file naming
if [[ "$FILE_PATH" == "$PROJECT_DIR"* ]]; then
    REL_PATH="${FILE_PATH#$PROJECT_DIR/}"
else
    REL_PATH="$FILE_PATH"
fi

# Create safe lock file name (replace path separators)
LOCK_FILE="$LOCK_DIR/$(echo "$REL_PATH" | tr '/' '_' | tr '\\' '_').lock"

# Check for concurrent edits
if [[ -f "$LOCK_FILE" ]]; then
    read -r LOCK_SESSION LOCK_TIME < <(python -c "
import json, sys
with open('$LOCK_FILE') as f:
    data = json.load(f)
print(data.get('session_id', ''), data.get('timestamp', 0))
" 2>/dev/null || echo " 0")

    CURRENT_TIME=$(date +%s)
    TIME_DIFF=$((CURRENT_TIME - LOCK_TIME))

    # Lock expires after 120 seconds
    if [[ "$TIME_DIFF" -lt 120 && "$LOCK_SESSION" != "$SESSION_ID" && -n "$LOCK_SESSION" ]]; then
        cat << EOF
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "File '$REL_PATH' is being edited by another agent. Wait for completion or coordinate."}}
EOF
        exit 0
    fi
fi

# Acquire lock atomically using mkdir
LOCK_DIR_ATOMIC="$LOCK_FILE.acquiring"
if mkdir "$LOCK_DIR_ATOMIC" 2>/dev/null; then
    python -c "
import json, time
data = {'session_id': '$SESSION_ID', 'timestamp': int(time.time()), 'file': '$REL_PATH'}
with open('$LOCK_FILE', 'w') as f:
    json.dump(data, f)
" 2>/dev/null
    rmdir "$LOCK_DIR_ATOMIC" 2>/dev/null
fi

# --- Secret Detection ---
# Skip test files (may contain mock secrets)
case "$FILE_PATH" in
    *test_*.py|*_test.py|*/tests/*.py|*tests.py) exit 0 ;;
    *.test.ts|*.spec.ts|*.test.js|*.spec.js) exit 0 ;;
esac

# Only check Write/Edit content for secrets
if [[ "$TOOL_NAME" == "Write" || "$TOOL_NAME" == "Edit" ]]; then
    SECRET_RESULT=$(echo "$INPUT" | python -c "
import json, sys, re

data = json.load(sys.stdin)
tool_input = data.get('tool_input', {})
content = tool_input.get('content', tool_input.get('new_string', ''))

if not content:
    sys.exit(0)

patterns = [
    ('generic secret', r'(?i)(api[_-]?key|secret|password|token|credential)\s*[=:]\s*[\"'\'']\s*[a-zA-Z0-9+/]{20,}'),
    ('AWS access key', r'AKIA[0-9A-Z]{16}'),
    ('JWT token', r'eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+'),
    ('GitHub personal access token', r'ghp_[a-zA-Z0-9]{36}'),
    ('private key', r'-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----'),
    ('exported secret', r'(?i)export\s+(API_KEY|SECRET|PASSWORD|TOKEN|CREDENTIAL|AWS_|PRIVATE_KEY)=[\"'\'']\s*[a-zA-Z0-9+/]{20,}'),
]

for name, pattern in patterns:
    if re.search(pattern, content):
        print(name)
        sys.exit(0)

print('')
" 2>/dev/null)

    if [[ -n "$SECRET_RESULT" ]]; then
        cat << EOF
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask", "permissionDecisionReason": "Potential $SECRET_RESULT detected in content being written. Please verify this is not sensitive data."}}
EOF
        exit 0
    fi
fi

exit 0
