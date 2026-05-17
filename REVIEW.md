# Review Rules

> Review-specific rules for Python/FastAPI projects.
> These rules are enforced only during `/review` execution, injected into specialist prompts.
> They supplement CLAUDE.md and `.claude/rules/` — they do not override them.
> **In any conflict, CLAUDE.md and PHILOSOPHY.md govern.**
> See ADR-0006 for the design rationale.
> **Prime Objective check**: For designs that touch attribution, consent of labor, value flow, or framework evolution (see CLAUDE.md "Prime Objective" section), apply the three-part test (a/b/c) as part of your review. Findings of the form "violates Prime Objective: extraction by test (b)" are first-class.

## Code Quality

1. All new public functions must have Google-style docstrings with Args, Returns, and Raises sections documented.
2. Functions exceeding 50 lines should be flagged for decomposition review — verify the length is justified by cohesion, not complexity.
3. Nested control flow deeper than 3 levels must be refactored using early returns, guard clauses, or extraction.
4. Magic numbers and string literals used more than once must be extracted to named constants.
5. All `TODO` and `FIXME` comments in new code must include a tracking reference (issue number, ADR, or ticket).

## API Design

6. All new FastAPI endpoints must have explicit `response_model` declarations.
7. All path and query parameters must use Pydantic `Field()` with descriptions for OpenAPI documentation.
8. Error responses must use the structured `AppError` hierarchy — no raw `HTTPException` with ad-hoc detail strings.
9. New endpoints must not introduce HTTP status codes not already used in the project without justification.

## Database

10. All new database queries must use parameterized statements — no f-string or `.format()` SQL construction.
11. Bulk operations must use batch queries rather than N+1 loops.
12. Schema changes must have a corresponding migration file or migration plan documented.

## Testing

13. New code must have tests that cover both the success path and at least one error/edge case.
14. Test files must mirror the source structure: `src/module.py` → `tests/test_module.py`. Framework infrastructure tests (validating `.claude/`, `scripts/`, or project-root artifacts) are exempt from this rule since they have no `src/` counterpart.
15. Mocked external dependencies must assert call arguments, not just call counts.
16. Files with test coverage below 80% must include a justification comment or a follow-up task.

## Security

17. All user-facing input must be validated at the API boundary using Pydantic models — no manual parsing of request bodies.
18. File path operations must use `pathlib.Path.resolve()` and validate against a whitelist of allowed directories.
19. Subprocess calls must use list arguments (not shell strings) and never interpolate user input.
20. New dependencies must be pinned to exact versions in requirements.txt.

## Documentation

21. New modules must have a module-level docstring explaining purpose and key classes/functions.
22. API endpoint changes must be reflected in any existing API documentation or examples.
23. Configuration changes must update relevant setup/deployment documentation.

## Performance

24. Database queries in request handlers must not perform unbounded result set fetches — use pagination or limits.
25. File I/O operations in request handlers should be flagged for async consideration.
26. New list/collection operations on potentially large datasets must document their time complexity or use streaming.
