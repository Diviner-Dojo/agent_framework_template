#!/bin/bash
# PreToolUse hook: Block pushing directly to main/master branch
# Enforces branch-based workflow to prevent accidental pushes to main.
#
# Rules:
#   - Commits on main: ALLOWED (may commit to then push a branch)
#   - Push to non-main branches: ALLOWED
#   - Push to main/master: BLOCKED with remediation instructions

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

# Only check git push commands
if ! echo "$COMMAND" | grep -qE '\bgit\s+push\b'; then
    exit 0
fi

# Get current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

IS_PUSH_TO_MAIN=false

# Check for explicit main/master in push command
if echo "$COMMAND" | grep -qE '\bgit\s+push\b.*\b(main|master)\b'; then
    IS_PUSH_TO_MAIN=true
fi

# Check for push without explicit branch while on main/master
if [[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "master" ]]; then
    # Detect bare push commands: "git push", "git push origin", "git push -u origin"
    if echo "$COMMAND" | grep -qE '\bgit\s+push\s*$'; then
        IS_PUSH_TO_MAIN=true
    elif echo "$COMMAND" | grep -qE '\bgit\s+push\s+(--[a-z-]+\s+)*[a-zA-Z0-9_-]+\s*$'; then
        IS_PUSH_TO_MAIN=true
    fi
fi

# Block if pushing to main
if [[ "$IS_PUSH_TO_MAIN" == "true" ]]; then
    cat << EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "BLOCKED: Cannot push directly to main branch. Use a feature branch workflow:\\n\\n1. Create a feature branch: git checkout -b feature/your-change\\n2. Commit your changes on the branch\\n3. Push the branch: git push -u origin feature/your-change\\n4. Create a PR for review\\n\\nCurrent branch: $CURRENT_BRANCH"
  }
}
EOF
    exit 0
fi

# Allow all other push commands
exit 0
