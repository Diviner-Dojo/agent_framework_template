# Coding Standards

## Python Conventions
- Python 3.11+ required
- All public functions and methods must have type annotations
- Use `ruff` for formatting and linting (run `ruff check` and `ruff format` before any review)
- Docstrings: Google style for all public functions, classes, and modules
- No bare `except:` — always catch specific exceptions
- No mutable default arguments (use `None` + assignment pattern)
- No global mutable state
- Prefer `pathlib.Path` over `os.path` for file operations
- Import ordering: stdlib, third-party, local (ruff enforces this)

## Naming
- Functions and variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private members: single leading underscore `_name`
- Descriptive names over abbreviations

## Structure
- Maximum function length: ~50 lines (guideline, not hard rule — prefer smaller)
- Single responsibility per function
- Prefer early returns over deep nesting
- Use Pydantic models for data validation at API boundaries
- Use dataclasses for internal data structures without validation needs
