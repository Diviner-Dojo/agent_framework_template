# Commit Protocol

## Before Every Commit

When the developer asks you to commit changes, or when you are about to suggest committing, follow this protocol:

### Step 1: Quality Gate (Required — Automated)
Run `python scripts/quality_gate.py` and verify all checks pass:
- Formatting (dart format)
- Linting (dart analyze)
- Tests (flutter test)
- Coverage (>= 80%)
- ADR completeness
- Review existence (for code changes)

If any check fails, fix the issues before proceeding. Use `--fix` to auto-remediate formatting and lint issues.

Note: The git pre-commit hook enforces this automatically. If the quality gate fails, git will block the commit. The review existence check will fail if code files are staged but no review report from today exists in `docs/reviews/`. Use `--skip-reviews` to bypass if needed.

### Step 1.5: Regression Test Verification (Required for bug fixes)
When committing a bug fix:
- Verify a regression test exists that fails without the fix and passes with it
- Verify the test is tagged with `@Tags(['regression'])`
- Add an entry to `memory/bugs/regression-ledger.md` documenting the bug, root cause, fix, and test location
- Commit fixes promptly — uncommitted fixes are invisible to git and WILL be lost across sessions

### Step 2: Code Review (Required for code changes)
For any change that modifies application source code (`lib/`), tests (`test/`), or framework infrastructure (`.claude/agents/`, `.claude/commands/`, `.claude/rules/`, `scripts/`):
- Run `/review <changed files>` to trigger multi-agent specialist review
- Wait for the review verdict before committing
- Address all **required changes** (blocking findings) before committing
- **Recommended improvements** (non-blocking) should be noted but do not block the commit

For documentation-only or trivial config changes, the quality gate alone is sufficient.

**Framework-only changes** (files under `.claude/`, `scripts/`, `docs/`) touching **more than 5 files** are treated as medium-risk and require `/review`. This prevents large framework changes from bypassing review under the "no product code" rationale.

**Known limitation**: The git pre-commit hook does not support `--skip-reviews` passthrough. When the hook blocks a commit legitimately exempted by the >5-file heuristic (i.e., fewer than 5 framework files changed), `--no-verify` is the current workaround. Always log the exemption reason in the commit message.

### Step 3: Education Gate (Required for medium-risk or above)
Required when the review verdict is medium-risk or above, or when the review explicitly recommends it:
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
