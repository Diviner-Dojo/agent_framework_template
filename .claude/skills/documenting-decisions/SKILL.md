---
name: documenting-decisions
description: Documentation policy — what must be documented and where (ADRs, reviews, discussions, promoted memory), the ADR scope classification (framework/project/hybrid), cross-project propagation, and CLAUDE.md maintenance triggers. Use when creating ADRs or reviews, or deciding where documentation belongs. Cross-refs the selecting-review-gates and syncing-framework-docs skills.
---

# Documentation Policy

## What Must Be Documented
- All architectural decisions → ADR in `docs/adr/`
- All multi-agent discussions → `discussions/` with events.jsonl + transcript.md
- All code reviews → review report in `docs/reviews/`
- All public APIs → docstrings in code + module-level docs
- All agent reflections → reflection files linked to discussions
- Sprint retrospectives → `docs/sprints/`
- All facilitator synthesis events must include a `## Request Context` section documenting developer framing (what was requested, scope, motivation, explicit constraints)

## Where
- ADRs: `docs/adr/ADR-NNNN-slug.md`
- Reviews: `docs/reviews/REV-YYYYMMDD-HHMMSS.md`
- Discussions: `discussions/YYYY-MM-DD/DISC-YYYYMMDD-HHMMSS-slug/`
- Promoted knowledge: `memory/` subdirectories
- Project conventions: `CLAUDE.md`

## Format Standard
- All structured artifacts use YAML frontmatter + Markdown body
- ADRs follow the template in `docs/templates/adr-template.md`
- Review reports follow `docs/templates/review-report-template.md`
- Reflections follow `docs/templates/reflection-template.md`

## ADR Scope Classification
- New ADRs must include a `scope:` field in frontmatter: `framework` (universal to all projects), `project` (this project only), or `hybrid` (universal principle, project-specific implementation)
- Framework-scoped ADRs are candidates for propagation to the template and shared-memory changelog
- When a framework ADR is accepted, add an entry to `~/.claude/shared-memory/FRAMEWORK_CHANGELOG.md`
- See DISC-20260411-171115 for the propagation architecture decision

## Cross-Project Propagation
- When a rule, command, or agent is created that is framework-universal, note it as a propagation candidate in the commit message
- Universal lessons from project-specific incidents belong in `~/.claude/shared-memory/universal-warnings.md`, not as propagated rule files
- The `/retro` command includes a cross-project knowledge check (Step 7) that prompts for shared-memory contributions

## CLAUDE.md Maintenance
- Update CLAUDE.md when project conventions change
- Update when new promoted rules are added to `.claude/rules/`
- Update when architectural boundaries shift (requires ADR)
- Every review comment about missing context is a signal that CLAUDE.md needs updating
