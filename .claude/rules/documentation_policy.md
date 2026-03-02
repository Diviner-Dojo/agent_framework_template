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

## CLAUDE.md Maintenance
- Update CLAUDE.md when project conventions change
- Update when new promoted rules are added to `.claude/rules/`
- Update when architectural boundaries shift (requires ADR)
- Every review comment about missing context is a signal that CLAUDE.md needs updating
