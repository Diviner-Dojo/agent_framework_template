---
description: "Full release workflow: quality gate, testing checklist, version bump, changelog, and rollback strategy."
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
argument-hint: "[--patch|--minor|--major] [--solo for direct-commit mode]"
---

# Ship Release Workflow

You are acting as the Facilitator. Guide the developer through a structured release process with automated change classification, review requirement detection, and version bumping.

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
6. **NEVER proceed with old version if `bump_version.py` fails**: Halt and report the error.

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

# Check bump_version.py exists (required for automated version bump)
if not pathlib.Path('scripts/bump_version.py').exists():
    errors.append('Missing scripts/bump_version.py — required for version bumping')

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

## Step 2: Auto-Classify Changes

Classify the changes since the last tag to determine review requirements and version bump type:

```bash
python -c "
import subprocess, re

# Get the last tag
result = subprocess.run(['git', 'describe', '--tags', '--abbrev=0'], capture_output=True, text=True)
last_tag = result.stdout.strip() if result.returncode == 0 else None
# If no tags exist, compare against the initial commit for complete diff
if last_tag:
    compare_ref = last_tag
else:
    result_root = subprocess.run(['git', 'rev-list', '--max-parents=0', 'HEAD'], capture_output=True, text=True)
    compare_ref = result_root.stdout.strip().split('\n')[0] if result_root.returncode == 0 else 'HEAD~10'

# Get changed files
result = subprocess.run(['git', 'diff', '--name-only', compare_ref, 'HEAD'], capture_output=True, text=True)
changed = [f for f in result.stdout.strip().split('\n') if f.strip()] if result.stdout.strip() else []

# Classify changes
code_files = [f for f in changed if f.startswith('src/') and not f.endswith(('.md', '.txt'))]
test_files = [f for f in changed if f.startswith('tests/')]
framework_files = [f for f in changed if f.startswith(('.claude/', 'scripts/'))]
config_files = [f for f in changed if f.endswith(('.toml', '.cfg', '.ini', '.yaml', '.yml', '.json'))]
doc_files = [f for f in changed if f.endswith('.md') or f.startswith('docs/')]

# Determine change type
# Per commit_protocol.md: code changes (src/ or tests/) require /review
# Per review_gates.md: framework changes > 5 files require /review
has_code = len(code_files) > 0 or len(test_files) > 0
has_framework = len(framework_files) > 0
large_framework = len(framework_files) > 5

if has_code:
    change_type = 'CODE'
    review_required = True
elif large_framework:
    change_type = 'FRAMEWORK (large)'
    review_required = True
elif has_framework:
    change_type = 'FRAMEWORK'
    review_required = False
else:
    change_type = 'CONFIG/DOCS'
    review_required = False

# Determine suggested bump
if any('migration' in f.lower() or 'schema' in f.lower() for f in changed):
    suggested_bump = 'MAJOR'
elif code_files:
    suggested_bump = 'MINOR'
else:
    suggested_bump = 'PATCH'

print(f'Last tag: {last_tag or \"(none)\"}')
print(f'Files changed: {len(changed)}')
print(f'  Code (src/): {len(code_files)}')
print(f'  Tests: {len(test_files)}')
print(f'  Framework (.claude/, scripts/): {len(framework_files)}')
print(f'  Config: {len(config_files)}')
print(f'  Docs: {len(doc_files)}')
print(f'Change type: {change_type}')
print(f'Review required: {review_required}')
print(f'Suggested bump: {suggested_bump}')
"
```

**Review requirement logic** (derived from `commit_protocol.md` and `review_gates.md`):
- **CODE changes** (`src/` or `tests/` files modified): `/review` always required — no exceptions
- **FRAMEWORK changes** (`.claude/`, `scripts/`) touching **> 5 files**: `/review` required (medium-risk per `review_gates.md`)
- **Small FRAMEWORK changes** (≤ 5 files): Quality gate sufficient
- **CONFIG/DOCS only**: Quality gate sufficient

If review is required but no review report exists for today in `docs/reviews/`, HALT and remind the developer to run `/review` first.

### Documentation Sync Check (FRAMEWORK changes only)

If the change type is FRAMEWORK or FRAMEWORK (large), verify that downstream documentation artifacts are in sync. Check the version references in:
- `docs/FRAMEWORK_SPECIFICATION.md` (frontmatter version, title)
- `docs/diviner-dojo-framework-presentation.html` (title, version badge, footer)
- `docs/how-to-use-presentation.html` (footer, stats)

If any artifact references an older framework version, WARN the developer and recommend updating per `.claude/rules/framework_doc_sync.md` before release.

## Step 3: Quality Gate

Run the full quality gate:

```bash
python scripts/quality_gate.py
```

If any check fails, HALT and fix before proceeding.

## Step 4: Testing Checklist

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

## Step 5: Version Bump

If a bump type is specified in the arguments (`--patch`, `--minor`, `--major`), use it. Otherwise, use the suggested bump from Step 2 after confirming with the developer.

**Major version bumps always require developer confirmation** regardless of auto-classification.

```bash
python scripts/bump_version.py --<patch|minor|major>
```

**If `bump_version.py` fails, HALT immediately.** Do NOT proceed with the old version. Report the error and ask the developer to fix pyproject.toml.

Read back the version to confirm:
```bash
python scripts/bump_version.py --read
```

## Step 6: Changelog

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

## Step 7: Rollback Strategy

Document the rollback strategy:

```markdown
### Rollback Strategy for v<version>

1. **Previous known-good version**: <previous version/commit>
2. **Database changes**: [Additive only / Requires reverse migration]
3. **Rollback command**: `git revert <commit>` or `git checkout <previous-tag>`
4. **Post-rollback verification**: Run smoke tests against previous version
5. **Data considerations**: [Any data transformations that need reversal]
```

## Step 8: Deploy Safety Review

Read and present the deploy safety rules:

```bash
cat memory/lessons/deploy-safety.md
```

Remind the developer of the key safety items relevant to this release.

## Step 9: Final Confirmation

Present a release summary:

1. **Version**: <new version>
2. **Mode**: Solo / Team
3. **Change type**: CODE / FRAMEWORK / CONFIG/DOCS
4. **Review status**: Completed / Not required
5. **Quality gate**: PASSED
6. **Testing checklist**: COMPLETED
7. **Rollback strategy**: DOCUMENTED
8. **Deploy safety**: REVIEWED

Ask the developer for final approval before proceeding.

## Step 10: Commit, Tag, and Release

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

Create the PR with a release summary:

```bash
gh pr create --title "Release v<version>" --body "$(cat <<'EOF'
## Release Summary

**Version**: v<version>
**Change type**: <type>
**Review**: <status>

### Changes
<summary of changes since last release>

### Rollback
<rollback strategy>

### Checklist
- [x] Quality gate passed
- [x] Testing checklist completed
- [x] Rollback strategy documented
EOF
)"
```

Tag after PR merge:
```bash
git tag -a v<version> -m "Release v<version>"
git push --tags
```

## Step 10.5: Update Spec Lifecycle

If the shipped changes were built against a spec (SPEC-*.md), update the spec's status:

```bash
python -c "
import pathlib, re
from datetime import datetime, timezone
# Identify the spec — check commit message or recent build discussions for spec reference
spec_path = pathlib.Path('<spec_file_path>')
if spec_path.exists():
    text = spec_path.read_text(encoding='utf-8')
    text = re.sub(r'^status:\s*.+$', 'status: complete', text, count=1, flags=re.MULTILINE)
    if 'completed_at:' not in text:
        text = re.sub(r'^(status: complete)$', r'\1\ncompleted_at: ' + datetime.now(timezone.utc).strftime('%Y-%m-%d'), text, count=1, flags=re.MULTILINE)
    spec_path.write_text(text, encoding='utf-8')
    print(f'Spec updated to complete: {spec_path.name}')
else:
    print('No spec path identified — skipping lifecycle update.')
"
```

If the spec cannot be identified automatically, ask the developer: "Was this work tracked against a spec? If so, which one?"

## Step 11: Post-Release Cleanup

After the release is confirmed:

```bash
# Pull latest main (after PR merge in team mode)
git checkout main
git pull

# Delete the release branch (team mode only)
git branch -d <release-branch>
```

Inform the developer the release is complete.
