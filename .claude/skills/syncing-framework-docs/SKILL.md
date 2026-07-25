---
name: syncing-framework-docs
description: Checklist for keeping downstream docs (FRAMEWORK_SPECIFICATION, presentation HTMLs) in sync when framework-defining files change. Use when editing .claude/agents, .claude/rules, .claude/commands, CLAUDE.md, PHILOSOPHY.md, or the project version — and during /review and /ship of framework changes.
---

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

When the trigger fires, review and update these four artifacts:

| Artifact | Path | Purpose |
|----------|------|---------|
| Framework Specification | `docs/FRAMEWORK_SPECIFICATION.md` | Authoritative full specification |
| Framework overview page | `docs/index.html` | Public "what it is" page (GitHub Pages entry point) |
| How-to-use page | `docs/how-to.html` | Public developer guide |
| Proof / case studies page | `docs/proof.html` | Evidence page — artifact counts + incident write-ups |

The two `docs/*-presentation.html` files are **redirect stubs** retained so older links
resolve. They carry no content and never need syncing.

## Sync Points

This table maps framework elements to the specific locations in each artifact that reference them. When an element changes, check every listed location.

Each HTML page also carries an authoring comment at the top listing the counts it states —
update that comment alongside the page so the next editor can diff intent against content.

| Framework Element | Specification | `index.html` | `how-to.html` | `proof.html` |
|-------------------|---------------|--------------|---------------|--------------|
| **Version number** | Frontmatter `version`, title, executive summary, footer | `<title>`, `.brand__ver`, hero kicker, footer | `.brand__ver`, footer | `.brand__ver`, footer |
| **Agent count** | Section 5 heading, roster table, implementation status | §05 heading + roster table | §01 "you get a team" card | — |
| **Agent model tiers** | Roster table, model-tier table, directory listing | §05 roster table tier badges | — | — |
| **Leadership hierarchy** | Section 5 leadership subsection | §05 heading + facilitator/steward rows | — | — |
| **Rule count** | Implementation status, directory listing | header comment | header comment | — |
| **Command count** | Section 6, implementation status | — | §11 heading + command tables | — |
| **Skill count** | Implementation status | — | §12 heading + skill lists | — |
| **Collaboration modes** | Section 4 | §05 "five collaboration modes" card | — | — |
| **Hook count** | Section 7, implementation status | §07 hooks card | §01 "you get gates" card | — |
| **Quality-gate checks** | Quality gate section | §07 gate card | §03 + §08 | — |
| **Principles** | Section 2 | §03 principles table | — | — |
| **Artifact counts** | — | hero stat strip | — | §01 record table |

**Artifact counts** (the hero stat strip on `index.html` and the table on `proof.html`) are the
one set of numbers that does *not* come from `.claude/`. They are file counts across the
template and its derived projects, and they go stale silently. Re-count them at `/ship` time
with the commands printed in the `proof.html` "How to reproduce these" callout, and update the
"Counted &lt;date&gt;" line on both pages.

## Enforcement

- **During `/review`**: When reviewing framework changes, verify that affected sync points have been updated. Flag stale documentation as an advisory finding.
- **During `/ship`**: The ship workflow checks for FRAMEWORK-type changes and verifies documentation sync before release.
- **Steward gate**: The Steward evaluates framework evolution proposals. Documentation sync is part of the completeness check.

## What This Rule Does NOT Cover

- Content accuracy of the documentation (that's the author's responsibility)
- CLAUDE.md updates (covered by the `documenting-decisions` skill)
- ADR creation for architectural changes (covered by the `selecting-review-gates` skill)
