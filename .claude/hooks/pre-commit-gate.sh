#!/bin/bash
# PreToolUse hook: Enforce quality gate before git commits
# Intercepts `git commit` commands and reminds the agent to run quality checks
#
# Uses a time-based state file (5-minute validity) to avoid re-checking
# within the same session after verification passes.

set -e

INPUT=$(cat)

# Only process Bash tool
TOOL_NAME=$(echo "$INPUT" | python -c "
import json, sys
data = json.load(sys.stdin)
print(data.get('tool_name', ''))
" 2>/dev/null || echo "")

if [[ "$TOOL_NAME" != "Bash" ]]; then
    exit 0
fi

# Extract the command
COMMAND=$(echo "$INPUT" | python -c "
import json, sys
data = json.load(sys.stdin)
print(data.get('tool_input', {}).get('command', ''))
" 2>/dev/null || echo "")

# Check if this is a git commit command
if ! echo "$COMMAND" | grep -qE '\bgit\s+commit\b'; then
    exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
STATE_DIR="$PROJECT_DIR/.claude/hooks/.state"
mkdir -p "$STATE_DIR"
VERIFICATION_FILE="$STATE_DIR/commit-verified"

# If verification was completed recently (within last 5 minutes), allow commit
if [[ -f "$VERIFICATION_FILE" ]]; then
    VERIFIED_TIME=$(cat "$VERIFICATION_FILE" 2>/dev/null || echo 0)
    CURRENT_TIME=$(date +%s)
    TIME_DIFF=$((CURRENT_TIME - VERIFIED_TIME))

    if [[ "$TIME_DIFF" -lt 300 ]]; then
        exit 0
    fi
fi

# Inject verification reminder
cat << EOF
{
  "hookSpecificOutput": {
    "additionalContext": "
---
[PRE-COMMIT VERIFICATION REQUIRED]

Before committing, you MUST complete these steps:

1. RUN QUALITY GATE:
   python scripts/quality_gate.py

   This checks: ruff format, ruff check, pytest, coverage >= 80%

2. FIX ALL FAILURES:
   - Use --fix flag: python scripts/quality_gate.py --fix
   - If tests fail, fix the code until they pass
   - Do NOT skip or disable failing checks

3. NEVER REMOVE OR SKIP TESTS:
   - Do NOT delete test files or test cases to make tests pass
   - Do NOT comment out failing tests
   - Fix the actual code issues instead

4. AFTER VERIFICATION SUCCEEDS:
   - Mark verification complete: echo \$(date +%s) > $STATE_DIR/commit-verified
   - Then proceed with the git commit

If you cannot fix a test legitimately, STOP and ask the user for guidance.
---"
  }
}
EOF
