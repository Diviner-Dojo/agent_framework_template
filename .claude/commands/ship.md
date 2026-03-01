---
description: "Ship changes end-to-end: quality gate, review gate, commit, branch, PR, merge, and sync back to main. Automates the full landing workflow."
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task", "Skill"]
argument-hint: "[optional commit description]"
---

# Ship Changes to Main

You are acting as the Facilitator. Execute the full ship workflow end-to-end: analyze changes, run gates, commit, create PR, merge, and sync.

## CRITICAL BEHAVIORAL RULES

These rules are pass/fail. Violating any of them is a workflow failure.

1. **NEVER skip the quality gate**: `python scripts/quality_gate.py` MUST pass before committing. No exceptions.
2. **NEVER skip review when required**: Code changes to `lib/` or `test/` ALWAYS require `/review`. Framework changes (`.claude/`, `scripts/`, `docs/`) touching >5 files require `/review`. Skipping review when required violates Principle #4.
3. **NEVER proceed after review rejection**: If `/review` returns **request-changes** or **reject**, STOP. Present the findings to the developer and do not continue the ship workflow.
4. **NEVER push directly to main**: Always use the feature branch + PR path. The pre-push-main-blocker hook enforces this, but do not attempt to bypass it.
5. **NEVER merge with failing checks**: If the PR has failing CI checks, do not merge. Investigate and fix first.
6. **ALWAYS clean up**: If the workflow fails partway through, clean up any created branches before stopping. Leave the working tree in a usable state.
7. **ALWAYS use `gh` with PATH**: All `gh` commands must be prefixed with `export PATH="$PATH:/c/Program Files/GitHub CLI" &&` to ensure the CLI is available.

## Pre-Flight Checks

Before starting, verify prerequisites:

```bash
python -c "
import pathlib, subprocess, sys
errors = []
# Check scripts exist
for script in ['scripts/quality_gate.py']:
    if not pathlib.Path(script).exists():
        errors.append(f'Missing required script: {script}')
# Check gh CLI is available
try:
    result = subprocess.run(
        ['gh', '--version'],
        capture_output=True, text=True, timeout=10,
        env={**__import__('os').environ, 'PATH': __import__('os').environ['PATH'] + ';C:\\\\Program Files\\\\GitHub CLI'}
    )
    if result.returncode != 0:
        errors.append('gh CLI not working')
except FileNotFoundError:
    errors.append('gh CLI not found — install from https://cli.github.com/')
# Check we are on main (standard starting point)
result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], capture_output=True, text=True)
branch = result.stdout.strip()
if branch != 'main' and branch != 'master':
    errors.append(f'Expected to be on main branch, but on: {branch}. Switch to main first.')
# Check for uncommitted changes (there should be some to ship)
result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
if not result.stdout.strip():
    errors.append('No changes to ship. Make changes first.')
if errors:
    print('PRE-FLIGHT FAILED:'); [print(f'  - {e}') for e in errors]; sys.exit(1)
else:
    print('Pre-flight checks passed.')
"
```

If pre-flight fails, present the errors to the developer and stop.

## Step 1: Analyze Changes

Understand what is being shipped:

1. Run `git status` to see all changed, staged, and untracked files.
2. Run `git diff` (unstaged) and `git diff --cached` (staged) to understand the content of changes.
3. Categorize the changes:
   - **Code changes**: Files under `lib/` or `test/`
   - **Framework changes**: Files under `.claude/`, `scripts/`, `docs/`
   - **Config/docs-only**: `pubspec.yaml`, `*.md` outside framework dirs, `.gitignore`, etc.
4. Count framework files changed (needed for review gate decision).

Present a brief summary of what will be shipped:
- Files changed (grouped by category)
- Lines added/removed
- Whether review will be required and why

## Step 1.5: Version Bump

Classify the change and bump the version automatically using `scripts/bump_version.py`:

### Classification Rules

| Change Type | Bump | Examples |
|---|---|---|
| **patch** | `--patch` | Bug fixes, framework-only changes, config, docs, test-only |
| **minor** | `--minor` | New files in `lib/`, new commands/screens, new features, new dependencies |
| **major** | `--major` | Breaking changes, database migrations, API contract changes |

- If ambiguous between patch and minor → default to **minor**
- If major → **confirm with the developer** before bumping
- The build number always increments automatically on any bump

### Execution

```bash
python scripts/bump_version.py --<patch|minor|major>
```

Print the new version to the developer:
```
Version bumped: 0.14.0+1 → 0.14.1+2
```

**Always stage `pubspec.yaml`** in Step 5a — the version bump must be included in the commit.

## Step 2: Quality Gate

Run the quality gate:

```bash
python scripts/quality_gate.py --fix
```

If the quality gate fails even after `--fix`:
- Present the failures to the developer
- Attempt to fix issues (formatting, lint errors, test failures)
- Re-run `python scripts/quality_gate.py` until it passes
- If you cannot fix an issue, STOP and ask the developer for guidance

After the quality gate passes, stamp the verification cache so the pre-commit hook does not re-prompt:

```bash
mkdir -p .claude/hooks/.state && echo $(date +%s) > .claude/hooks/.state/commit-verified
```

## Step 3: Review Gate

Determine whether a review is required based on the change categories from Step 1:

### Review Required
- Any file under `lib/` or `test/` is modified → run `/review`
- Framework files (`.claude/`, `scripts/`, `docs/`) and **more than 5 files** changed → run `/review`

### Review Skipped (log reason)
- Only documentation files changed (`.md` files not under `.claude/` or `scripts/`)
- Only config files changed (`pubspec.yaml`, `.gitignore`, etc.)
- Framework changes touching **5 or fewer files**
- Single file changes to non-code files

If review is required, run `/review` on the changed files using the Skill tool:
```
Skill(skill="review", args="<space-separated list of changed files>")
```

After the review completes:
- **approve** or **approve-with-changes** → continue to Step 4
- **request-changes** or **reject** → STOP. Present the review findings and tell the developer what needs to be fixed. Do not continue.

If review is skipped, log the reason (e.g., "Review skipped: config-only change" or "Review skipped: 3 framework files, below >5 threshold").

## Step 4: Education Gate

If a review was run in Step 3 AND the review verdict is medium-risk or above:
- Inform the developer that an education gate is recommended
- Ask the developer if they want to run `/walkthrough` and `/quiz` now, or defer
- If deferred, note the deferral (it must be completed before the next phase per Principle #6)

If the review was low-risk, or no review was run, skip this step.

## Step 5: Commit

### 5a: Stage Files

Stage all relevant changed files. Be selective — do NOT stage:
- `.env` files or anything matching secret patterns
- Large binary files not intended for the repo
- Temporary/debug files (e.g., `logcat_*.txt`, `test_output*.txt`)

Use specific file paths rather than `git add -A`:
```bash
git add <file1> <file2> ...
```

### 5b: Generate Commit Message

If the user provided a `[description]` argument, use it as the commit message.

If no description was provided, analyze the diff to generate a concise commit message:
- Summarize the nature of the change (new feature, bug fix, enhancement, refactor, etc.)
- Focus on the "why" not the "what"
- Keep it to 1-2 sentences
- Do NOT add `Co-Authored-By` — this will be appended automatically

### 5c: Commit

```bash
git commit -m "$(cat <<'EOF'
<commit message>

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

## Step 6: Branch + Push + PR

### 6a: Create Feature Branch

Derive a branch slug from the commit message:
- Lowercase
- Replace spaces and special characters with hyphens
- Truncate to 50 characters
- Prefix with `feature/`

```bash
git checkout -b feature/<slug>
```

### 6b: Push

```bash
export PATH="$PATH:/c/Program Files/GitHub CLI" && git push -u origin feature/<slug>
```

### 6c: Create PR

Generate a PR title (short, under 70 chars) and body from the change analysis:

```bash
export PATH="$PATH:/c/Program Files/GitHub CLI" && gh pr create --title "<PR title>" --body "$(cat <<'EOF'
## Summary
<1-3 bullet points describing the change>

## Quality
- Quality gate: passed
- Review: <completed / skipped (reason)>
- Education gate: <completed / skipped / deferred>

## Test plan
- <relevant test steps>

🤖 Shipped with `/ship` via [Claude Code](https://claude.com/claude-code)
EOF
)"
```

## Step 7: Merge + Sync

### 7a: Merge the PR

```bash
export PATH="$PATH:/c/Program Files/GitHub CLI" && gh pr merge --merge
```

If merge fails (e.g., CI checks pending), wait briefly and retry once. If still failing, present the issue to the developer.

### 7b: Sync Back to Main

```bash
git checkout main && git pull origin main
```

### 7c: Clean Up Feature Branch

```bash
git branch -d feature/<slug>
```

## Step 8: Present to Developer

Present the completed workflow summary:

1. **Changes shipped**: Brief description of what was landed
2. **Quality gate**: Passed (link to `metrics/quality_gate_log.jsonl` entry)
3. **Review**: Verdict and report path, or reason for skip
4. **PR**: Link to the merged PR on GitHub
5. **Current state**: Confirmed on main, up to date with remote

If any step was skipped or deferred, note it clearly.

## Error Recovery

If the workflow fails at any point after creating a branch:

1. Note which step failed and why
2. If a branch was created but not merged:
   - Ask the developer: fix and retry, or abandon?
   - If abandoning: `git checkout main && git branch -D feature/<slug>`
   - If the branch was pushed: `export PATH="$PATH:/c/Program Files/GitHub CLI" && gh pr close --delete-branch` (if PR exists)
3. Present clear next steps to the developer
