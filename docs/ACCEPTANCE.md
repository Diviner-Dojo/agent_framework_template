# Acceptance Criteria

## Permanent Quality Gates (always required)

- [ ] `ruff format` — no formatting violations
- [ ] `ruff check` — no lint violations
- [ ] `pytest tests/` — all tests pass
- [ ] Coverage >= 80% for new/modified code
- [ ] ADR exists for any architectural decision
- [ ] Version bump if releasing (`pyproject.toml`)

## Session-Specific Criteria

<!-- Fill in at session start. What must be true for this session's work to be "done"? -->

### Goal: [describe what this session should accomplish]

| # | Criterion | Verification Command | Status |
|---|-----------|---------------------|--------|
| 1 | [expected outcome] | [command to verify] | [ ] |
| 2 | [expected outcome] | [command to verify] | [ ] |

### Definition of Done

- [ ] All session-specific criteria verified with commands above
- [ ] Quality gate passes: `python scripts/quality_gate.py`
- [ ] BUILD_STATUS.md updated with completed work
- [ ] No uncommitted changes that should be committed
