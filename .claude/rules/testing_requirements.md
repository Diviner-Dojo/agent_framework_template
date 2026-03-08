# Testing Requirements

## Coverage
- Unit tests for all business logic functions
- Integration tests for all API endpoints
- Target >= 80% code coverage for new and modified code

## Test Quality
- Every test must have meaningful assertions (not just "no exception thrown")
- Test both success paths and error/edge cases
- Edge cases to always consider: empty inputs, boundary values, None/null, duplicate entries, not-found scenarios

## Test Isolation
- Tests must not depend on shared mutable state
- Each test must set up and tear down its own data
- Use fixtures for common setup patterns
- Tests must be deterministic — no flaky tests

## Test Organization
- Test files mirror source file structure: `src/routes.py` -> `tests/test_routes.py`
- Use descriptive test names: `test_create_todo_with_empty_title_returns_422`
- Group related tests in classes when it improves readability
- Use `pytest.mark.parametrize` for testing multiple input variations

## Running Tests
- `pytest tests/` runs the full suite (deterministic tests only)
- `pytest tests/ -v` for verbose output
- `pytest tests/ --cov=src` for coverage report
- `pytest tests/ --run-llm` includes tests that call real LLM APIs
- `pytest tests/ --run-slow` includes slow-running tests

## Test Markers
- `@pytest.mark.uses_llm` — marks tests that call real LLM APIs (skipped by default, requires `--run-llm`)
- `@pytest.mark.slow` — marks slow tests (skipped by default, requires `--run-slow`)
- `@pytest.mark.regression` — marks regression tests that guard against specific fixed bugs
- The quality gate runs deterministic tests only. LLM-dependent and slow tests are opt-in.

## Regression Tests
- Every bug fix MUST include a regression test that would fail under the old buggy code
- Tag regression tests with `@pytest.mark.regression` and include a comment referencing the bug
- Regression test names should describe the bug being prevented: `test_speed_setting_persists_across_audio_source_changes`
- When modifying a file that has existing regression tests, verify they still pass and still test the right behavior
- Regression tests must NOT be deleted or weakened without explicit developer approval
