# Agent Notes

Persistent cross-session knowledge base for AI agents. Read before starting work. Add entries after each session.

This document occupies a middle tier between session-scoped `BUILD_STATUS.md` (ephemeral) and curated `memory/` Layer 3 (promoted). It captures failure patterns, useful commands, and known quirks that are too specific for promotion but too valuable to lose.

## Session Log

<!-- Add a brief entry after each significant session.
Format:
### [Date] — [Brief description]
- What was done
- What was learned
- Any open issues
-->

## Common Failure Patterns

<!-- Document recurring failures with actionable solutions.
Format:
### [Failure Name]
- **Symptom**: What you observe
- **Solution**: How to fix it
- **Prevention**: How to avoid it in the future
-->

## Useful Commands

<!-- Commands that are non-obvious but frequently needed.
Format:
- `command here` — what it does and when to use it
-->

- `python scripts/quality_gate.py --fix` — auto-fix formatting and lint issues
- `python scripts/quality_gate.py --skip-reviews` — skip review existence check
- `pytest tests/ -v --tb=short` — verbose test output with short tracebacks
- `ruff check src/ --fix` — auto-fix lint violations

## Known Quirks

<!-- Platform-specific or project-specific gotchas that aren't bugs but cause confusion.
-->
