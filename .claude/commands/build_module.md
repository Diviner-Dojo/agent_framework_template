---
description: "Build a module from a spec with integrated quality gates. Generates code, runs tests, triggers review, and activates education gate."
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task"]
argument-hint: "[spec file path or module description]"
---

# Module Construction with Quality Gates

You are acting as the Facilitator. Build code against an approved spec with integrated quality controls.

## CRITICAL BEHAVIORAL RULES

These rules are pass/fail. Violating any of them is a workflow failure.

1. **NEVER skip tests**: Every module MUST have tests before declaring completion. No untested code passes this gate.
2. **NEVER skip the linter**: Ruff check and format MUST run and pass before triggering review.
3. **NEVER declare completion with failing tests**: If tests fail, fix the implementation and re-run. Do NOT move to the review step with failing tests.
4. **ALWAYS follow the spec**: Implementation must satisfy all acceptance criteria in the spec. If the spec is ambiguous, ask the developer — do not guess.
5. **ALWAYS recommend the education gate**: Every build MUST end with an education gate recommendation.

## Pre-Flight Checks

Before starting the build, verify prerequisites:

```bash
python -c "
import pathlib, sys
errors = []
for d in ['src', 'tests']:
    if not pathlib.Path(d).exists():
        errors.append(f'Missing required directory: {d}')
for rule in ['.claude/rules/coding_standards.md', '.claude/rules/security_baseline.md', '.claude/rules/testing_requirements.md']:
    if not pathlib.Path(rule).exists():
        errors.append(f'Missing required rule file: {rule}')
if errors:
    print('PRE-FLIGHT FAILED:'); [print(f'  - {e}') for e in errors]; sys.exit(1)
else:
    print('Pre-flight checks passed.')
"
```

If pre-flight fails, tell the developer what's missing and suggest running `/onboard` to set up the framework structure.

## Step 1: Read the Spec

If a spec file path is provided, read it. If not, check `docs/sprints/` for the most recent approved spec, or ask the developer what to build.

## Step 2: Generate Implementation

Based on the spec:
1. Create or modify source files in `src/`
2. Follow the coding standards in `.claude/rules/coding_standards.md`
3. Follow the security baseline in `.claude/rules/security_baseline.md`
4. Include type annotations on all public functions
5. Include Google-style docstrings

## Step 3: Generate Tests

Create tests in `tests/` that cover:
1. All acceptance criteria from the spec
2. Edge cases (empty inputs, boundary values, error states)
3. At least one integration test per endpoint/interface
4. Follow testing requirements in `.claude/rules/testing_requirements.md`

## Step 4: Run Tests

```bash
pytest tests/ -v --tb=short
```

If tests fail, fix the implementation and re-run until all pass.

## Step 5: Run Linter

```bash
ruff check src/ tests/
ruff format --check src/ tests/
```

Fix any issues found.

## Step 6: Trigger Review

Tell the developer: "Module built and tests passing. Run `/review <files>` to trigger the specialist review panel."

## Step 7: Education Gate

After review, recommend the developer run `/walkthrough` and `/quiz` on the new module to verify their understanding.
