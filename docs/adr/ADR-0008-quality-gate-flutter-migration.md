---
adr_id: ADR-0008
title: "Quality Gate Migration from Python/ruff to Flutter/Dart"
status: accepted
date: 2026-02-19
decision_makers: [architecture-consultant, facilitator]
discussion_id: DISC-20260219-175738-phase1-spec-review
supersedes: null
risk_level: medium
confidence: 0.90
tags: [quality-gate, infrastructure, dart, flutter, commit-protocol]
---

## Context

The project's quality gate (`scripts/quality_gate.py`) was originally built to validate Python/FastAPI code using ruff (formatting + linting), pytest (tests), and pytest-cov (coverage). Following ADR-0002 (Flutter/Dart tech stack adoption), the application code is now Dart — but the quality gate script still validates Python.

The quality gate is a critical framework component: it runs automatically via the git pre-commit hook and blocks commits that fail formatting, linting, tests, or coverage checks. It is referenced in CLAUDE.md's Commit Protocol section and enforced by `.claude/hooks/pre-commit-gate.sh`.

The `scripts/` directory itself remains Python — the capture pipeline (`create_discussion.py`, `write_event.py`, `close_discussion.py`) and other framework utilities are Python scripts that must continue working. Only the application code checks need to change.

## Decision

Rewrite `scripts/quality_gate.py` to validate **Flutter/Dart application code** while preserving the existing CLI interface and Python infrastructure:

| Check | Old (Python) | New (Flutter/Dart) |
|-------|-------------|-------------------|
| Formatting | `ruff format --check src/ tests/` | `dart format --set-exit-if-changed lib/ test/` |
| Linting | `ruff check src/ tests/` | `dart analyze lib/ test/` |
| Tests | `pytest tests/` | `flutter test` |
| Coverage | `pytest --cov=src --cov-fail-under=80` | `flutter test --coverage` + parse `coverage/lcov.info` |
| ADR check | (unchanged) | (unchanged) |
| Auto-fix | `ruff format` + `ruff check --fix` | `dart format` + `dart fix --apply` |

**Preserve**: `--fix`, `--skip-format`, `--skip-lint`, `--skip-tests`, `--skip-coverage`, `--skip-adrs` flags.

**Update**: `SRC_DIR` → `lib/`, `TESTS_DIR` → `test/` (singular, Flutter convention). `validate_directories()` checks for `.dart` files instead of `.py`.

**Also required**: Update CLAUDE.md's Quality Gate section to document the new Dart commands.

## Alternatives Considered

### Alternative 1: Replace quality_gate.py with a Dart-native script
- **Pros**: Single language for the entire project; could use `dart analyze` directly as the entry point
- **Cons**: The capture pipeline scripts are Python — the framework's tooling layer would be split across two languages; Python is the right tool for orchestration scripts
- **Reason rejected**: The quality gate is a framework utility, not application code. Keeping it in Python maintains consistency with the rest of `scripts/` and avoids requiring Dart to run CI tooling.

### Alternative 2: Use a Makefile or shell script instead
- **Pros**: Language-agnostic; simpler for basic check orchestration
- **Cons**: Loses the structured output formatting, skip flags, and fix mode; harder to maintain and extend; Windows compatibility issues with make
- **Reason rejected**: The existing Python script is well-structured with good CLI interface; rewriting in shell would be a regression in maintainability

## Consequences

### Positive
- Quality gate enforces Dart code standards consistently with the commit protocol
- Pre-commit hook blocks malformed commits automatically
- Coverage threshold (80%) applies to Flutter test coverage
- Auto-fix mode (`--fix`) works with Dart tooling

### Negative
- Quality gate now depends on Flutter SDK being on PATH (must include `export PATH="$PATH:/c/src/flutter/bin"` or equivalent)
- Coverage parsing changes from pytest-cov (Python) to lcov (Flutter) format — the parsing logic must be rewritten
- Old Python app code in `src/` and `tests/` is no longer validated (those directories are removed in Phase 1 Task 1)

### Neutral
- The ADR completeness check is unchanged (it reads YAML frontmatter, not application code)
- The git pre-commit hook mechanism is unchanged — only what the quality gate checks changes
- Framework Python scripts (`scripts/*.py`) are not subject to quality gate checks (they never were — only `src/` and `tests/` were checked)

## Linked Discussion
See: discussions/2026-02-19/DISC-20260219-175738-phase1-spec-review/
