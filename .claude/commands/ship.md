---
description: "Full release workflow: quality gate, testing checklist, version bump, changelog, and rollback strategy."
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
argument-hint: "[version number, e.g., 1.2.0] [--solo for direct-commit mode]"
---

# Ship Release Workflow

You are acting as the Facilitator. Guide the developer through a structured release process.

## Workflow Mode Detection

Parse the arguments to determine the workflow mode:

- **`--solo`** flag present → **Solo mode**: Direct commit + tag on current branch. No PR, no `gh` CLI required. For solo developers who own their main branch.
- **No `--solo` flag** → **Team mode**: Branch-based workflow with PR. Requires `gh` CLI.

Announce the detected mode before proceeding.

## CRITICAL BEHAVIORAL RULES

These rules are pass/fail. Violating any of them is a workflow failure.

1. **NEVER ship with failing quality gate**: All checks must pass before proceeding.
2. **NEVER skip the testing checklist**: Every release must verify critical paths.
3. **ALWAYS document a rollback strategy**: No release goes out without a way back.
4. **NEVER skip `/review` for code changes**: If `src/` files are included in this release, a review must exist.
5. **Team mode only — NEVER push directly to main**: Use branch-based workflow with PR.

## Step 1: Pre-Flight Validation

Verify prerequisites before starting the release workflow:

```bash
python -c "
import pathlib, subprocess, sys

solo_mode = '--solo' in sys.argv or '$ARGUMENTS'.find('--solo') >= 0
errors = []

# Check required scripts exist
for script in ['scripts/quality_gate.py', 'scripts/init_db.py']:
    if not pathlib.Path(script).exists():
        errors.append(f'Missing required script: {script}')

# Check gh CLI is available (team mode only)
if not solo_mode:
    try:
        subprocess.run(['gh', 'auth', 'status'], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        errors.append('gh CLI not authenticated (run: gh auth login)')

# Check branch state
result = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True)
branch = result.stdout.strip()
if not solo_mode and branch in ('main', 'master'):
    errors.append(f'On {branch} branch — create a release branch first (or use --solo)')

# Check working tree is clean
result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
if result.stdout.strip():
    errors.append('Working tree has uncommitted changes — commit or stash first')

# Check pyproject.toml exists
if not pathlib.Path('pyproject.toml').exists():
    errors.append('Missing pyproject.toml — cannot determine current version')

# Check bump_version.py exists
if not pathlib.Path('scripts/bump_version.py').exists():
    print('NOTE: scripts/bump_version.py not found — version bump will be manual')

if errors:
    print('PRE-FLIGHT FAILED:')
    for e in errors:
        print(f'  - {e}')
    sys.exit(1)
else:
    mode_label = 'SOLO (direct commit)' if solo_mode else f'TEAM (branch: {branch})'
    print(f'Pre-flight passed. Mode: {mode_label}')
"
```

If pre-flight fails, HALT and address the issues before proceeding.

## Step 2: Quality Gate

Run the full quality gate:

```bash
python scripts/quality_gate.py
```

If any check fails, HALT and fix before proceeding.

## Step 3: Testing Checklist

Present the following checklist and verify each item with the developer:

```markdown
### Release Testing Checklist

- [ ] All unit tests pass (`pytest tests/ -v`)
- [ ] All integration tests pass
- [ ] Manual smoke test of critical paths:
  - [ ] Application starts without errors
  - [ ] Health endpoint responds (`/health` or equivalent)
  - [ ] Core CRUD operations work
  - [ ] Authentication flow works (if applicable)
  - [ ] Error responses return expected format
- [ ] No new deprecation warnings in test output
- [ ] Database migrations apply cleanly (`python scripts/init_db.py`)
- [ ] Environment variables documented and verified
- [ ] Dependencies pinned in requirements.txt
```

Ask the developer to confirm each item or flag any that need attention.

## Step 4: Version Bump

Determine the version bump type from the changes since the last tag:

```bash
python -c "
import subprocess, re

# Get the last tag
result = subprocess.run(['git', 'describe', '--tags', '--abbrev=0'], capture_output=True, text=True)
last_tag = result.stdout.strip() if result.returncode == 0 else None

if last_tag:
    # Get changed files since last tag
    result = subprocess.run(['git', 'diff', '--name-only', last_tag, 'HEAD'], capture_output=True, text=True)
    changed = result.stdout.strip().split('\n') if result.stdout.strip() else []
    new_src = [f for f in changed if f.startswith('src/') and not any(f.endswith(e) for e in ['.md', '.txt'])]
    print(f'Last tag: {last_tag}')
    print(f'Files changed: {len(changed)}')
    print(f'New/modified src files: {len(new_src)}')
    if any('migration' in f.lower() or 'schema' in f.lower() for f in changed):
        print('Suggested bump: MAJOR (schema/migration changes detected)')
    elif new_src:
        print('Suggested bump: MINOR (new source files)')
    else:
        print('Suggested bump: PATCH (bug fixes / docs / config)')
else:
    print('No previous tags found — this will be the first release')
"
```

If a version is specified in the arguments, use it. Otherwise, present the suggestion and ask the developer to confirm.

**If `scripts/bump_version.py` exists:**
```bash
python scripts/bump_version.py --<patch|minor|major>
```

**Otherwise**, update the version manually in:
1. `pyproject.toml` — `version = "<new_version>"`
2. Any `__version__` variables in source code
3. `CLAUDE.md` — framework version if applicable

## Step 5: Changelog

Check if a changelog exists. If so, add an entry:

```markdown
## [<version>] - <date>

### Added
- [New features from recent commits]

### Changed
- [Modifications from recent commits]

### Fixed
- [Bug fixes from recent commits]
```

If no changelog exists, ask the developer if they want one created.

## Step 6: Rollback Strategy

Document the rollback strategy:

```markdown
### Rollback Strategy for v<version>

1. **Previous known-good version**: <previous version/commit>
2. **Database changes**: [Additive only / Requires reverse migration]
3. **Rollback command**: `git revert <commit>` or `git checkout <previous-tag>`
4. **Post-rollback verification**: Run smoke tests against previous version
5. **Data considerations**: [Any data transformations that need reversal]
```

## Step 7: Deploy Safety Review

Read and present the deploy safety rules:

```bash
cat memory/lessons/deploy-safety.md
```

Remind the developer of the key safety items relevant to this release.

## Step 8: Final Confirmation

Present a release summary:

1. **Version**: <new version>
2. **Mode**: Solo / Team
3. **Changes included**: <summary of commits since last release>
4. **Quality gate**: PASSED
5. **Testing checklist**: COMPLETED
6. **Rollback strategy**: DOCUMENTED
7. **Deploy safety**: REVIEWED

Ask the developer for final approval before proceeding.

## Step 9: Commit, Tag, and Release

### Solo Mode

Commit the version bump and changelog directly, then tag:

```bash
git add pyproject.toml CHANGELOG.md
git commit -m "Release v<version>"
git tag -a v<version> -m "Release v<version>"
```

Inform the developer:
- The commit and tag have been created locally
- Run `git push && git push --tags` to publish

### Team Mode

With developer approval:

```bash
git tag -a v<version> -m "Release v<version>"
```

Inform the developer:
- The tag has been created locally
- They need to `git push --tags` to publish
- Remind them NOT to push directly to main (use branch-based workflow)
