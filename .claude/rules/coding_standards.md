# Coding Standards

## Dart Conventions
- Dart 3.x with sound null safety
- Use `dart format` for formatting (enforced by quality gate and auto-format hook)
- Use `dart analyze` for linting (zero errors required)
- Doc comments (`///`) for all public classes, methods, and top-level functions
- No bare `catch` — always catch specific exception types (e.g., `on FormatException`)
- Prefer `final` for local variables that are not reassigned
- Use `late` sparingly — prefer nullable types with null checks over `late` initialization
- Prefer `const` constructors where possible

## Naming
- Functions, variables, parameters: `camelCase`
- Classes, enums, typedefs, extensions: `PascalCase`
- Constants: `camelCase` (Dart convention, not UPPER_SNAKE_CASE)
- Private members: single leading underscore `_name`
- Libraries and file names: `snake_case`
- Descriptive names over abbreviations

## Structure
- Maximum function length: ~50 lines (guideline, not hard rule — prefer smaller)
- Single responsibility per function
- Prefer early returns over deep nesting
- Use drift models for database entities
- Use Riverpod providers for dependency injection and state management
- Prefer immutable data classes — use `copyWith` patterns for state updates

## Python Conventions (framework scripts only)
- Python 3.11+ for scripts in `scripts/`
- Type annotations on all public functions
- Use `pathlib.Path` over `os.path`
- No bare `except:` — catch specific exceptions
