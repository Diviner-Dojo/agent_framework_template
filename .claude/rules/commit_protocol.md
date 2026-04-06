# Commit Protocol

## Before Every Commit

When the developer asks you to commit changes, or when you are about to suggest committing, follow this protocol:

### Step 1: Quality Gate (Required — Automated)
Run `python scripts/quality_gate.py` and verify all checks pass:
- Formatting (ruff format)
- Linting (ruff check)
- Tests (pytest)
- Coverage (>= 80%)
- ADR completeness
- Review existence (for code changes)

If any check fails, fix the issues before proceeding. Use `--fix` to auto-remediate formatting and lint issues.

Note: The git pre-commit hook enforces this automatically. If the quality gate fails, git will block the commit. The review existence check will fail if code files are staged but no review report from today exists in `docs/reviews/`. Use `--skip-reviews` to bypass if needed.

### Step 1.5: Solution-Path Check (Advisory)
Before committing, briefly check whether this change solves a problem that should be captured as a solution path:
- Does this commit implement a non-trivial approach that future builds should know about?
- Were alternative approaches tried and rejected?
- If yes, note this for capture in Step 3.5.

### Step 1.7: Regression Test Verification (Required for bug fixes)
When committing a bug fix:
- Verify a regression test exists that fails without the fix and passes with it
- Verify the test is tagged with `@pytest.mark.regression`
- Add an entry to `memory/bugs/regression-ledger.md` documenting the bug, root cause, fix, and test location
- Commit fixes promptly — uncommitted fixes are invisible to git and WILL be lost across sessions

### Step 2: Code Review (Required for code changes)
For any change that modifies application source code (`src/`), tests (`tests/`), or framework infrastructure (`.claude/agents/`, `.claude/commands/`, `.claude/rules/`, `scripts/`):
- Run `/review <changed files>` to trigger multi-agent specialist review
- Wait for the review verdict before committing
- Address all **required changes** (blocking findings) before committing
- **Recommended improvements** (non-blocking) should be noted but do not block the commit

For documentation-only or trivial config changes, the quality gate alone is sufficient.

**Framework-only changes** (files under `.claude/`, `scripts/`, `docs/`) touching **more than 5 files** are treated as medium-risk and require `/review`. This prevents large framework changes from bypassing review under the "no product code" rationale.

### Step 3: Education Gate (Required for medium-risk or above)
Required when the review verdict is medium-risk or above, or when the review explicitly recommends it:
- Run `/walkthrough <files>` for the developer
- Run `/quiz <files>` for comprehension assessment
- Complete the education gate before committing

### Step 3.5: Solution-Path Capture (Advisory)
If Step 1.5 flagged this commit as containing a noteworthy solution path:
- Add an entry to `memory/projects/_self.md` under `## Solution Paths` documenting the problem, what was tried, what was chosen, and why.
- Use compound tags from `memory/projects/TAXONOMY.md` (e.g., `[auth/session-management]`).
- If an approach was tried and found broken, add it to `memory/bugs/regression-ledger.md` under `## Known-Broken Approaches`.

This step is advisory — it captures knowledge for future builds but does not block the commit.

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
