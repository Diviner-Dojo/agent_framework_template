#!/bin/bash
# Safeguard: Prevent derived projects from pushing to the template repo.
#
# Usage: Add to derived project's .git/hooks/pre-push or .claude/hooks/
#
# This script checks if the push target is the template repo and blocks it.
# Derived projects should push to their own remote, not the template.

TEMPLATE_REPO_PATTERNS=(
    "agent_framework_template"
    "agent-framework-template"
)

# Read push destination from stdin (git pre-push hook protocol)
while read local_ref local_sha remote_ref remote_sha; do
    REMOTE_URL=$(git remote get-url "$1" 2>/dev/null || echo "")

    for pattern in "${TEMPLATE_REPO_PATTERNS[@]}"; do
        if echo "$REMOTE_URL" | grep -qi "$pattern"; then
            echo "ERROR: Attempting to push to the template repository!"
            echo "  Remote: $1 ($REMOTE_URL)"
            echo "  This appears to be the framework template repo."
            echo ""
            echo "If this is a derived project, you should push to your own remote."
            echo "If you intentionally need to push to the template, use:"
            echo "  git push --no-verify $1 <branch>"
            exit 1
        fi
    done
done

exit 0
