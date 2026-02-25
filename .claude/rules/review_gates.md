# Review Gates

## Minimum Quality Thresholds
- Test coverage >= 80% for new and modified code
- No critical or high-severity security findings left unaddressed
- All public functions must have docstrings
- All new modules must have module-level docstrings
- No failing tests in the test suite

## Architectural Gates
- Any architectural change requires an ADR in `docs/adr/`
- New module boundaries require architecture-consultant review
- Dependency additions require security-specialist review

## Education Gates
- Required for all complex or high-risk changes before merge
- Four-step gate: walkthrough → quiz → explain-back → merge
- Quiz pass threshold: 70%
- Bloom's level mix: 60-70% Understand/Apply, 30-40% Analyze/Evaluate
- At least 1 debug scenario and 1 change-impact question per quiz
- Educational intensity adapts to demonstrated competence (scaffolding fades)

## Review Activation

### Risk Tiers and Agent Selection

| Risk | Mode | Agent Count | Mandatory Agents | Examples |
|---|---|---|---|---|
| Low | Ensemble | 2-3 | qa-specialist + 1 domain specialist | Docs, config, simple fixes |
| Medium | Structured Dialogue | 3-4 | qa-specialist, architecture-consultant + 1-2 domain | New features, refactoring, dependency updates |
| High | Dialectic or Adversarial | 4-5 | qa-specialist, architecture-consultant, security-specialist, independent-perspective | Security code, architecture changes, API contracts |
| Critical | Adversarial | 5-6 | Full panel | Auth, payments, data migration, infrastructure |

### Domain Specialist Triggers

| Change Type | Specialist to Include |
|---|---|
| Database, ORM, migrations | performance-analyst |
| API routes, middleware | architecture-consultant |
| Network, auth, API security | security-specialist |
| New module or significant feature | architecture-consultant, docs-knowledge |
| UI/UX with accessibility concerns | ux-evaluator, qa-specialist |
| External API integration | security-specialist, performance-analyst |
| Framework infrastructure (.claude/, scripts/) | docs-knowledge |

The facilitator assesses risk and selects specialists per the table above.
