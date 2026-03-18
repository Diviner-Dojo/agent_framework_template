---
adr_id: ADR-0004
title: "Adopt automated classification and version bumping in /ship"
status: accepted
date: 2026-03-13
decision_makers: [facilitator, architecture-consultant, security-specialist]
discussion_id: DISC-20260313-205202-build-journal-pattern-adoption
supersedes: null
risk_level: medium
confidence: 0.85
tags: [ship, automation, versioning, workflow]
---

## Context

The `/ship` command was a guided checklist that required the developer to manually classify changes, decide whether review was needed, and determine the version bump type. This created friction in the release workflow and left room for inconsistency — the same set of changes could be classified differently depending on developer attention.

Additionally, `/ship` referenced `scripts/bump_version.py` which did not exist, making the version bump step manual every time.

The agentic journal (a derived project) had evolved `/ship` into an automated decision engine that classified changes, auto-determined review requirements, and auto-bumped versions. This pattern proved effective in practice and was identified for backporting to the template.

## Decision

Rebuild `/ship` with three automation layers:

1. **Auto-classification**: Categorize changes into CODE (src/ or tests/), FRAMEWORK (.claude/, scripts/), or CONFIG/DOCS based on git diff against the last tag. The classification logic derives from and references `commit_protocol.md` and `review_gates.md` rather than encoding independent thresholds.

2. **Auto-review-requirement**: Determine whether `/review` is required based on the classification:
   - CODE changes → always require review (per `commit_protocol.md`)
   - FRAMEWORK changes > 5 files → require review (per `review_gates.md` medium-risk threshold)
   - Small FRAMEWORK or CONFIG/DOCS → quality gate sufficient

3. **Auto-version-bump**: Use `scripts/bump_version.py` with `--patch`, `--minor`, or `--major` flags. Major bumps always require developer confirmation. If `bump_version.py` fails, the workflow halts — never proceed with the old version.

The `--solo` mode is preserved for developers who own their main branch and prefer direct-commit workflow without PRs.

## Alternatives Considered

### Alternative 1: Keep /ship as a guided checklist
- **Pros**: Simpler command, developer stays in control of every decision
- **Cons**: Inconsistent classification, manual version bumps, friction in frequent releases
- **Reason rejected**: The manual approach had already been superseded in practice by the journal's automated version. The friction cost was real — developers would skip `/ship` and commit directly.

### Alternative 2: Full automation with no developer confirmation
- **Pros**: Fastest possible release flow
- **Cons**: Major version bumps and review bypasses could happen without developer awareness
- **Reason rejected**: Major version bumps have downstream consequences that warrant explicit confirmation. The hybrid approach (auto-suggest, confirm major) balances speed with safety.

### Alternative 3: Separate /ship-auto and /ship-manual commands
- **Pros**: No breaking change for developers used to the old workflow
- **Cons**: Two commands to maintain, unclear which to use, feature drift between them
- **Reason rejected**: The automated version is strictly better — it preserves all manual overrides (explicit --patch/--minor/--major flags) while adding automation as the default path.

## Consequences

### Positive
- Consistent change classification across all releases
- Review requirements enforced by the same rules as `commit_protocol.md` (no drift)
- Version bumps are reliable and validated (semver regex check before write)
- Fixes the broken `bump_version.py` reference that existed since framework inception

### Negative
- The inline Python scripts in the command make the `.md` file larger and harder to review visually
- Classification heuristics (e.g., "migration" in filename → MAJOR) are imperfect approximations

### Neutral
- The `--solo` flag behavior is unchanged — solo developers experience the same workflow as before, plus automation

## Linked Discussion
See: discussions/2026-03-13/DISC-20260313-205202-build-journal-pattern-adoption/
