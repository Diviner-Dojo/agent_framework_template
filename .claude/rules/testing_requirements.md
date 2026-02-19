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
- Test files mirror source file structure: `src/routes.py` → `tests/test_routes.py`
- Use descriptive test names: `test_create_todo_with_empty_title_returns_422`
- Group related tests in classes when it improves readability
- Use `pytest.mark.parametrize` for testing multiple input variations

## Running Tests
- `pytest tests/` runs the full suite
- `pytest tests/ -v` for verbose output
- `pytest tests/ --cov=src` for coverage report
