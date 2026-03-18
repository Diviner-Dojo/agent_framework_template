# Framework Documentation Sync

> Ensures downstream documentation artifacts stay in sync when the framework evolves.
> Prevents the recurring problem of framework version bumps leaving specs and presentations stale.

## Trigger

This rule activates when any change touches framework-defining files:
- `.claude/agents/` — agent definitions (count, roles, model tiers)
- `.claude/rules/` — auto-loaded standards (count, new rules)
- `.claude/commands/` — slash commands (count, new commands)
- `CLAUDE.md` — project constitution
- `PHILOSOPHY.md` — framework philosophy
- `pyproject.toml` — project version

## Documentation Artifacts to Sync

When the trigger fires, review and update these three artifacts:

| Artifact | Path | Purpose |
|----------|------|---------|
| Framework Specification | `docs/FRAMEWORK_SPECIFICATION.md` | Authoritative full specification |
| Framework Presentation | `docs/diviner-dojo-framework-presentation.html` | Presentation deck for stakeholders |
| How-to-Use Presentation | `docs/how-to-use-presentation.html` | Developer onboarding walkthrough |

## Sync Points

This table maps framework elements to the specific locations in each artifact that reference them. When an element changes, check every listed location.

| Framework Element | Specification | Presentation HTML | How-to-Use HTML |
|-------------------|---------------|-------------------|-----------------|
| **Version number** | Frontmatter `version`, title, executive summary, footer | `<title>`, version badge, footer | Footer |
| **Agent count** | Section 5 heading, roster table, implementation status | Slide 5 heading, directory tree | Stats card |
| **Agent model tiers** | Roster table, model-tier table, directory listing | Slide 5 agent cards (badge + tier class) | — |
| **Leadership hierarchy** | Section 5 leadership subsection | Slide 5 heading and agent cards | — |
| **Rule count** | Implementation status, directory listing | Directory tree slide | — |
| **Command count** | Section 6, implementation status | — | Stats card, cheat sheet |
| **Collaboration modes** | Section 4 | Slide 6 | — |
| **Hook count** | Section 7, implementation status | Slide 8 | — |
| **Principles** | Section 2 | Slide 3 | — |

## Enforcement

- **During `/review`**: When reviewing framework changes, verify that affected sync points have been updated. Flag stale documentation as an advisory finding.
- **During `/ship`**: The ship workflow checks for FRAMEWORK-type changes and verifies documentation sync before release.
- **Steward gate**: The Steward evaluates framework evolution proposals. Documentation sync is part of the completeness check.

## What This Rule Does NOT Cover

- Content accuracy of the documentation (that's the author's responsibility)
- CLAUDE.md updates (covered by `documentation_policy.md`)
- ADR creation for architectural changes (covered by `review_gates.md`)
