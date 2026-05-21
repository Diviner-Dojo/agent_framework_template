# Project Reference

Quick-reference for AI agents. Documents project-specific conventions that diverge from or extend the generic framework.

## Project Identity

- **Name**: [Your Project Name]
- **Type**: [API / CLI / Library / Full-stack]
- **Entry point**: `src/main.py` (or equivalent)
- **Config**: `pyproject.toml` + `requirements.txt`

## Key Divergences from Framework Defaults

<!-- Document where this project intentionally differs from the template.
Format:
| Area | Template Default | This Project | Why |
|------|-----------------|--------------|-----|
-->

*No divergences yet — this is the template itself.*

## Common Agent Tasks

<!-- Map common requests to the right approach.
Format:
- "Add a new API endpoint" → create route in src/routes/, model in src/models/, test in tests/
- "Fix a failing test" → read the test, read the source, run `pytest tests/test_file.py -v`
-->

## Environment Setup

```bash
pip install -r requirements.txt
pytest tests/               # run tests
python scripts/quality_gate.py  # full quality check
ruff format src/ tests/     # format code
```
