---
adr_id: ADR-0027
title: "Automatic semantic versioning with build tracking"
status: accepted
date: 2026-02-28
decision_makers: [facilitator, developer]
discussion_id: null  # Inline decision during implementation — no formal /deliberate
supersedes: null
risk_level: low
confidence: 0.90
tags: [versioning, deployment, devops]
---

## Context

The app has been at `version: 1.0.0+1` (Flutter scaffold default) through 14 phases of development. The Settings screen showed a hardcoded `'Version 1.0.0'`. Deploy logs had no version field. There was no way to check what version was installed on the phone. The `/ship` command automated the full commit-PR-merge workflow but didn't bump versions.

This meant:
- No traceability from a running app back to its source version
- Deploy logs couldn't distinguish which build was deployed
- The version number was meaningless (1.0.0 implies production-ready, but the app is pre-1.0)
- Manual version management would be forgotten or inconsistent

## Decision

Implement automatic semantic versioning:

1. **Starting version**: `0.14.0+1` — Phase 14 of development, `0.x` = pre-1.0, `+1` = first tracked build
2. **Bump script**: `scripts/bump_version.py` handles `--patch`, `--minor`, `--major`, `--build`, and `--read` via regex on `pubspec.yaml`
3. **Build number**: Always increments on any bump (monotonically increasing across all bump types)
4. **Dynamic display**: Settings screen reads version from `package_info_plus` at runtime via `appVersionProvider`
5. **Deploy logging**: `scripts/deploy.py` includes `version` in JSONL records and supports `--check-version` to compare device vs pubspec
6. **Auto-bump in /ship**: Step 1.5 classifies changes (patch/minor/major) and bumps before quality gate

### Classification Rules

| Change Type | Bump |
|---|---|
| Bug fixes, framework-only, config, docs | patch |
| New files in `lib/`, new commands/screens, new features | minor |
| Breaking changes, migrations, API contract changes | major |

Ambiguous → default to minor. Major requires developer confirmation.

## Alternatives Considered

### Alternative 1: Manual version bumping
- **Pros**: Developer has full control
- **Cons**: Will be forgotten, inconsistent, adds friction
- **Reason rejected**: The whole point of the agentic framework is to automate mechanical tasks

### Alternative 2: CI-based versioning (e.g., semantic-release)
- **Pros**: Industry standard for CI/CD pipelines
- **Cons**: Requires CI infrastructure we don't have; our deploy is local `flutter run`
- **Reason rejected**: Premature — we deploy from a local machine, not CI. Can adopt later if needed.

### Alternative 3: Git tag-based versioning
- **Pros**: Version tied to git history
- **Cons**: Requires git tags to be managed, doesn't integrate with Flutter's pubspec version field
- **Reason rejected**: Flutter reads version from pubspec.yaml; git tags would be a parallel system to keep in sync

## Consequences

### Positive
- Every deploy is traceable to a specific version
- Settings screen shows real version to the user
- Deploy logs include version for debugging production issues
- `/ship` automates version bumping — zero friction
- `--check-version` flag enables quick device verification

### Negative
- Adds `package_info_plus` dependency (~lightweight, well-maintained)
- Version bumps create noise in pubspec.yaml diffs (one line per ship)

### Neutral
- Build number is monotonically increasing but not globally unique (resets if manually edited)
- Pre-1.0 versioning (`0.x`) signals that the app is not production-ready
- Regex-based pubspec editing assumes a specific `version:` line format; non-standard formatting would break the script (mitigated by 10 unit tests)

## Linked Discussion
No formal discussion captured — decision made inline during implementation (2026-02-28). The classification rules in Step 1.5 of `.claude/commands/ship.md` and the review at DISC-20260301-021110-review-semantic-versioning constitute the operational record.
