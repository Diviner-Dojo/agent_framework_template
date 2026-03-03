---
description: "Full release workflow: quality gate, testing checklist, version bump, changelog, and rollback strategy."
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
argument-hint: "[version number, e.g., 1.2.0]"
---

# Ship Release Workflow

You are acting as the Facilitator. Guide the developer through a structured release process.

## CRITICAL BEHAVIORAL RULES

1. **NEVER ship with failing quality gate**: All checks must pass before proceeding.
2. **NEVER skip the testing checklist**: Every release must verify critical paths.
3. **ALWAYS document a rollback strategy**: No release goes out without a way back.

## Step 1: Pre-Flight Quality Gate

Run the full quality gate:

```bash
python scripts/quality_gate.py
```

If any check fails, HALT and fix before proceeding.

## Step 2: Testing Checklist

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

## Step 3: Version Bump

If a version is specified, update the version in:

1. `pyproject.toml` — `version = "<new_version>"`
2. Any `__version__` variables in source code
3. `CLAUDE.md` — framework version if applicable

If no version is specified, read the current version and suggest the next version based on the changes:
- **Patch** (x.y.Z): Bug fixes, documentation
- **Minor** (x.Y.0): New features, non-breaking changes
- **Major** (X.0.0): Breaking changes, major refactors

## Step 4: Changelog

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

## Step 5: Rollback Strategy

Document the rollback strategy:

```markdown
### Rollback Strategy for v<version>

1. **Previous known-good version**: <previous version/commit>
2. **Database changes**: [Additive only / Requires reverse migration]
3. **Rollback command**: `git revert <commit>` or `git checkout <previous-tag>`
4. **Post-rollback verification**: Run smoke tests against previous version
5. **Data considerations**: [Any data transformations that need reversal]
```

## Step 6: Deploy Safety Review

Read and present the deploy safety rules:

```bash
cat memory/lessons/deploy-safety.md
```

Remind the developer of the key safety items relevant to this release.

## Step 7: Final Confirmation

Present a release summary:

1. **Version**: <new version>
2. **Changes included**: <summary of commits since last release>
3. **Quality gate**: PASSED
4. **Testing checklist**: COMPLETED
5. **Rollback strategy**: DOCUMENTED
6. **Deploy safety**: REVIEWED

Ask the developer for final approval before tagging.

## Step 8: Tag and Release

With developer approval:

```bash
git tag -a v<version> -m "Release v<version>"
```

Inform the developer:
- The tag has been created locally
- They need to `git push --tags` to publish
- Remind them NOT to push directly to main (use branch-based workflow)
