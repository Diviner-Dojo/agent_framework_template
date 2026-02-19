# Commit Protocol

## Before Every Commit

When the developer asks you to commit changes, or when you are about to suggest committing, follow this protocol:

### Step 1: Quality Gate (Required — Automated)
Run `python scripts/quality_gate.py` and verify all checks pass:
- Formatting (ruff format)
- Linting (ruff check)
- Tests (pytest)
- Coverage (>= 80%)

If any check fails, fix the issues before proceeding. Use `--fix` to auto-remediate formatting and lint issues.

Note: The git pre-commit hook enforces this automatically. If the quality gate fails, git will block the commit.

### Step 2: Code Review (Required for code changes)
For any change that modifies application source code (`src/`), tests (`tests/`), or framework infrastructure (`.claude/agents/`, `.claude/commands/`, `.claude/rules/`, `scripts/`):
- Run `/review <changed files>` to trigger multi-agent specialist review
- Wait for the review verdict before committing
- Address all **required changes** (blocking findings) before committing
- **Recommended improvements** (non-blocking) should be noted but do not block the commit

For documentation-only or trivial config changes, the quality gate alone is sufficient.

### Step 3: Education Gate (When recommended by review)
If the review recommends an education gate (medium-risk or above):
- Run `/walkthrough <files>` for the developer
- Run `/quiz <files>` for comprehension assessment
- Complete the education gate before committing

### Step 4: Update BUILD_STATUS.md
After committing, update BUILD_STATUS.md with:
- Move the completed task from "In Progress" to "Recently Completed"
- Update "Modified Files" section
- Clear any resolved blockers

## What NOT to Do
- Do NOT commit with `--no-verify` unless the developer explicitly requests it and explains why
- Do NOT skip the review for code changes — Principle #4 requires independent evaluation
- Do NOT commit files that contain secrets (.env, credentials, API keys)
- Do NOT amend previous commits unless the developer explicitly requests it
