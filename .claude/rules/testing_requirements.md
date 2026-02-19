# Testing Requirements

## Coverage
- Unit tests for all business logic functions
- Widget tests for all UI components
- Target >= 80% code coverage for new and modified code
- Generated files (`*.g.dart`, `*.freezed.dart`) excluded from coverage calculations

## Test Quality
- Every test must have meaningful assertions (not just "no exception thrown")
- Test both success paths and error/edge cases
- Edge cases to always consider: empty inputs, boundary values, null, duplicate entries, not-found scenarios
- Use `expect()` with specific matchers — avoid bare `isTrue`/`isFalse` when a more descriptive matcher exists

## Test Isolation
- Tests must not depend on shared mutable state
- Use in-memory databases for DAO tests: `AppDatabase.forTesting(NativeDatabase.memory())`
- Each test must set up and tear down its own data
- Tests must be deterministic — no flaky tests
- Use `setUp()` and `tearDown()` for common setup patterns

## Test Organization
- Test files mirror source file structure: `lib/utils/keyword_extractor.dart` → `test/utils/keyword_extractor_test.dart`
- Use descriptive test names: `'creates session with correct default values'`
- Group related tests with `group()` when it improves readability
- Widget tests use `testWidgets()` and `WidgetTester`

## Running Tests
- `flutter test` runs the full suite
- `flutter test -v` for verbose output
- `flutter test --coverage` generates `coverage/lcov.info`
- `flutter test test/specific_test.dart` runs a single test file
- `python scripts/quality_gate.py` runs tests as part of the full quality gate

## Test Tags (when LLM-dependent tests are introduced)
- Use `@Tags(['uses_llm'])` to mark tests that call real LLM APIs
- Use `@Tags(['slow'])` to mark slow-running tests
- The quality gate runs deterministic tests only. LLM-dependent and slow tests are opt-in.
