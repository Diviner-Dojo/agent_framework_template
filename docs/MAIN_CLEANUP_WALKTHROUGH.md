---
created: 2026-03-08
purpose: Walkthrough of origin/main cleanup to remove agentic_journal pollution
status: pre-execution
---

# Main Branch Cleanup Walkthrough

## Problem

`origin/main` (commit af63db0) was accidentally polluted with the agentic_journal Flutter app.
The branch `framework-enhancements-knowledge-pipeline` (commit 9f7594e) has the clean framework code.
PR #68 is blocked until main is cleaned.

## Current State

- **origin/main**: 1,113 files (framework + journal app mixed together)
- **feature branch**: 186 files (clean framework only)

## Files to REMOVE (927 files)

### Flutter App Directories (entire directories)

| Directory | Files | Description |
|-----------|-------|-------------|
| `android/` | 27 | Android build config |
| `ios/` | 40 | iOS build config |
| `lib/` | 127 | Dart source code (the journal app) |
| `linux/` | 10 | Linux build config |
| `macos/` | 28 | macOS build config |
| `web/` | 7 | Web build config |
| `windows/` | 18 | Windows build config |
| `assets/` | 1 | App assets |
| `integration_test/` | 3 | Flutter integration tests |
| `supabase/` | 11 | Supabase backend config |
| `test/` | 167 | Flutter/Dart test suite |

**Subtotal: 439 files**

### Journal-Specific Root Files (11 files)

| File | Description |
|------|-------------|
| `.metadata` | Flutter metadata |
| `pubspec.yaml` | Dart package manifest |
| `pubspec.lock` | Dart lock file |
| `analysis_options.yaml` | Dart analysis config |
| `build.yaml` | Dart build config |
| `dart_test.yaml` | Dart test config |
| `screenshot.png` | App screenshot |
| `DART_DEFINE_FLAGS.md` | Dart compile flags doc |
| `CAPABILITY_STATUS.md` | Journal capability tracking |
| `WALKTHROUGH.md` | Journal walkthrough (root-level) |
| `FRAMEWORK_QUIZ.md` | Journal quiz (root-level) |

Note: `EDUCATOR_NOTES.md`, `EDUCATION_GATE_START.md`, `EDUCATION_GATE_MANIFEST.md` exist on both branches — evaluate whether they're framework-generic or journal-specific.

### Journal-Specific Scripts (4 files)

| File | Description |
|------|-------------|
| `scripts/bump_version.py` | Journal version bumping |
| `scripts/deploy.py` | Journal deployment |
| `scripts/test_bump_version.py` | Tests for bump_version |
| `scripts/test_on_emulator.py` | Emulator test runner |

### Journal-Specific .claude Rule (1 file)

| File | Description |
|------|-------------|
| `.claude/rules/capability_protection.md` | Journal capability tracking rule |

### Journal-Specific Docs (~158 files)

Only the following docs exist on the feature branch and should be KEPT:
- `docs/FRAMEWORK_SPECIFICATION.md` (exists on both)
- `docs/adr/.gitkeep` (exists on both)
- `docs/adr/ADR-0001-adopt-agentic-framework.md` (exists on both — but may differ)
- `docs/templates/*` (5 template files — exist on both)
- `docs/sprints/.gitkeep` (exists on both)

Everything else in docs/ on main is journal-specific:
- `docs/PHASE3-QUICK-REFERENCE.md`
- `docs/adr/ADR-0002-flutter-dart-tech-stack.md` through ADR-0035+ (33 journal ADRs)
- `docs/reviews/REV-*` (all review reports from journal development)
- `docs/sprints/RETRO-*`, `docs/sprints/SPEC-*`, `docs/sprints/META-REVIEW-*` (all journal sprints)
- `docs/unified-project-analysis.md`
- `docs/walkthroughs/*`

### Journal-Specific Discussions (~352 files)

The feature branch has discussions from:
- `2026-02-18/` (4 discussions, framework-related)
- `2026-02-19/` (8 discussions, framework analysis)
- `2026-03-03/` (1 discussion, framework review)
- `2026-03-07/` (1 discussion, steward review)

All other discussions on main are journal-specific (dates 2026-02-19 through 2026-03-05 that don't match the feature branch).

### Journal-Specific Metrics Entries

| File | Action |
|------|--------|
| `metrics/deploy_log.jsonl` | Remove entirely (journal-specific) |
| `metrics/emulator_test_log.jsonl` | Remove entirely (journal-specific) |

## Files to KEEP (framework infrastructure)

### .claude/ (49 files on main, minus 1 journal rule = 48 kept)

All agents, commands, hooks, rules (except capability_protection.md), skills, settings.

### scripts/ (23 of 27 kept)

All pipeline scripts except the 4 journal-specific ones listed above.

### memory/ (9 files)

All memory files including adoption-log.md, deploy-safety.md, regression-ledger.md.

### metrics/ (3 of 5 kept)

- `metrics/.gitkeep`
- `metrics/knowledge_pipeline_log.jsonl`
- `metrics/quality_gate_log.jsonl`

### docs/ (~7 files kept from main)

- `docs/FRAMEWORK_SPECIFICATION.md`
- `docs/adr/.gitkeep`
- `docs/adr/ADR-0001-adopt-agentic-framework.md`
- `docs/sprints/.gitkeep`
- `docs/templates/` (5 files)

### discussions/ (1 file kept)

- `discussions/.gitkeep`

(The feature branch's discussions will come via PR #68, not this cleanup.)

### Root files kept

- `.gitignore`
- `BUILD_STATUS.md`
- `CLAUDE.md`
- `README.md`
- `pyproject.toml`
- `requirements.txt`

### Root files — need decision

| File | On main? | On branch? | Recommendation |
|------|----------|------------|----------------|
| `EDUCATOR_NOTES.md` | Yes | Yes | Keep if framework-generic |
| `EDUCATION_GATE_START.md` | Yes | Yes | Keep if framework-generic |
| `EDUCATION_GATE_MANIFEST.md` | Yes | Yes | Keep if framework-generic |
| `WALKTHROUGH.md` | Yes (journal) | Yes (framework) | Keep branch version via PR |
| `FRAMEWORK_QUIZ.md` | Yes (journal) | Yes (framework) | Keep branch version via PR |

## Execution Strategy

1. Create cleanup branch from origin/main: `git checkout -b cleanup/remove-journal-files origin/main`
2. Remove all journal directories and files (listed above)
3. Clean journal-specific metrics files
4. Verify framework integrity (all kept files intact)
5. Commit the removal
6. Force-update main: `git push origin cleanup/remove-journal-files:main --force`
7. After main is clean, PR #68 should merge cleanly

## Safeguard: Prevent Re-Pollution

Add a pre-receive hook or GitHub branch protection rule to prevent derived projects from pushing to the template repo. Options:
1. GitHub branch protection: require PR reviews for main
2. Custom pre-push hook that warns when pushing to the template remote
3. Add the template remote as read-only in derived projects

## Verification Checklist

After cleanup, verify:
- [ ] No Flutter/Dart files remain
- [ ] No journal-specific ADRs remain
- [ ] No journal-specific discussions remain
- [ ] .claude/ has 49 files (48 from main + steward comes via PR)
- [ ] scripts/ has 23 pipeline utility files
- [ ] Quality gate scripts are intact
- [ ] CLAUDE.md is intact
- [ ] .gitignore is intact
