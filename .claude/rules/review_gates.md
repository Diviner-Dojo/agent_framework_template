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
- Low risk (docs, config, simple fixes): Ensemble mode, low intensity
- Medium risk (new features, refactoring): Structured Dialogue, medium intensity
- High risk (security, architecture, distributed systems): Dialectic or Adversarial, high intensity
- The facilitator assesses risk and selects the appropriate mode
