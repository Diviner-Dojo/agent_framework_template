#!/bin/bash
# PreToolUse hook: Enforce quality gate before git commits
# Intercepts `git commit` commands and reminds the agent to run quality checks
#
# Also checks:
# - Regression ledger: warns if staged files appear in memory/bugs/regression-ledger.md
# - Review reminder: warns if code files are staged but no review exists for today
#
# Uses a time-based state file (5-minute validity) to avoid re-checking
# within the same session after verification passes.

# NOTE: Do not use set -e in hooks. It causes silent failures — if any command
# exits non-zero the script terminates immediately without useful output.
# Use per-command error handling instead (|| echo "", 2>/dev/null, etc.)

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

# Build additional context from regression ledger and review checks
ADDITIONAL_WARNINGS=""

# --- Regression ledger check ---
# Cross-reference staged files against regression ledger using full relative paths
LEDGER_FILE="$PROJECT_DIR/memory/bugs/regression-ledger.md"
if [[ -f "$LEDGER_FILE" ]]; then
    REGRESSION_MATCHES=""
    # Safe iteration using process substitution to avoid subshell variable scoping
    while IFS= read -r staged_file; do
        if [[ -z "$staged_file" ]]; then
            continue
        fi
        # Use fixed-string grep to prevent regex injection from filenames
        if grep -qF "$staged_file" "$LEDGER_FILE" 2>/dev/null; then
            REGRESSION_MATCHES="${REGRESSION_MATCHES}
  - $staged_file (has regression test entry in ledger)"
        fi
    done < <(git diff --cached --name-only 2>/dev/null)
    if [[ -n "$REGRESSION_MATCHES" ]]; then
        ADDITIONAL_WARNINGS="${ADDITIONAL_WARNINGS}

5. REGRESSION LEDGER WARNING:
   The following staged files have entries in the regression ledger.
   Verify their regression tests still pass:${REGRESSION_MATCHES}"
    fi
fi

# --- Review reminder ---
# Check if code files (src/ or tests/) are staged but no review exists for today
# Uses process substitution to keep variable in current shell scope
HAS_CODE_FILES=false
while IFS= read -r staged_file; do
    if [[ "$staged_file" =~ ^(src/|tests/) ]]; then
        HAS_CODE_FILES=true
        break
    fi
done < <(git diff --cached --name-only 2>/dev/null)

if [[ "$HAS_CODE_FILES" == "true" ]]; then
    TODAY=$(date +%Y%m%d)
    REVIEW_DIR="$PROJECT_DIR/docs/reviews"
    REVIEW_EXISTS=false
    if [[ -d "$REVIEW_DIR" ]]; then
        # Check for any review file matching today's date
        for review_file in "$REVIEW_DIR"/REV-${TODAY}-*.md; do
            if [[ -f "$review_file" ]]; then
                REVIEW_EXISTS=true
                break
            fi
        done
    fi
    if [[ "$REVIEW_EXISTS" == "false" ]]; then
        ADDITIONAL_WARNINGS="${ADDITIONAL_WARNINGS}

6. REVIEW REMINDER:
   Code files (src/ or tests/) are staged but no review report exists for today.
   Consider running /review before committing (per commit_protocol.md)."
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
   - Mark verification complete: echo \$(date +%s) > \"$STATE_DIR/commit-verified\"
   - Then proceed with the git commit

If you cannot fix a test legitimately, STOP and ask the user for guidance.${ADDITIONAL_WARNINGS}
---"
  }
}
EOF
