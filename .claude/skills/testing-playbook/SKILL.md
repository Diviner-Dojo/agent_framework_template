---
name: testing-playbook
description: "Testing strategies and patterns for Python/pytest projects. Reference when writing tests, reviewing test coverage, or designing test strategies."
---

# Testing Playbook

## pytest Patterns

### Test Client for FastAPI
```python
import pytest
from httpx import ASGITransport, AsyncClient
from src.main import app

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
```

### Fixtures for Test Data
```python
@pytest.fixture
async def sample_todo(client):
    response = await client.post("/todos", json={"title": "Test Todo"})
    return response.json()
```

### Parametrize for Input Variations
```python
@pytest.mark.parametrize("title,expected_status", [
    ("Valid Title", 201),
    ("", 422),
    ("x" * 201, 422),
])
async def test_create_todo_validation(client, title, expected_status):
    response = await client.post("/todos", json={"title": title})
    assert response.status_code == expected_status
```

## Test Categories

### Unit Tests
- Test individual functions in isolation
- Mock external dependencies
- Fast execution, high specificity

### Integration Tests
- Test API endpoints end-to-end
- Use test database
- Verify request → processing → response → database state

### Edge Case Tests
Always test:
- Empty inputs (empty string, empty list, None)
- Boundary values (0, -1, MAX_INT, very long strings)
- Not-found scenarios (invalid IDs, deleted resources)
- Duplicate operations (create same thing twice)
- Concurrent access (if applicable)

## Test Naming Convention
```
test_<action>_<scenario>_<expected_result>
```
Examples:
- `test_create_todo_with_valid_data_returns_201`
- `test_create_todo_with_empty_title_returns_422`
- `test_get_todo_with_invalid_id_returns_404`

## Assertion Patterns

### Verify Response Shape
```python
data = response.json()
assert "id" in data
assert data["title"] == "Test Todo"
assert data["completed"] is False
```

### Verify Database State
```python
# After creating, verify it's retrievable
get_response = await client.get(f"/todos/{data['id']}")
assert get_response.status_code == 200
```

### Verify Side Effects
```python
# After deletion, verify it's gone
await client.delete(f"/todos/{todo_id}")
get_response = await client.get(f"/todos/{todo_id}")
assert get_response.status_code == 404
```

## Running Tests
- `pytest tests/ -v` — verbose output
- `pytest tests/ --cov=src` — with coverage
- `pytest tests/ -k "test_create"` — filter by name
- `pytest tests/ -x` — stop on first failure

## Quality-Gate Conventions (SPEC-20260716-233400, R3.1-R3.4)

For derived projects consuming `scripts/quality_gate.py`:

- **Greppable failure lines**: every failing check emits exactly one
  `ERROR <check>: <reason>` line on stderr (match with `^ERROR \w+: `);
  warnings follow the same shape (`WARN <check>: <reason>`). Parse these,
  not the colored human summary.
- **Gate log is additive-only**: `metrics/quality_gate_log.jsonl` records gain
  fields (`profile`, `baseline_debt_count`, `rebaseline`, `fast`) but existing
  fields never change or disappear (schema-pinned by test). Check statuses:
  `pass | fail | skipped | disabled` — `disabled` = turned off by the gate
  profile (by-design; does not demote `overall`).
- **`--fast` is for mid-build iteration only**: a deterministic ~25% sample of
  test files (stable across runs; changes only when the file list changes).
  It logs `fast: true`, skips coverage, and is NEVER commit-gate evidence —
  the pre-commit hook must never pass it.
- **Failing tool output is truncated** to the last 20 lines with a rerun
  pointer — rerun the underlying command for full output.
- **Debt baseline** (`config/gate_baseline.json`, python-fastapi profile):
  fingerprints are `(check, posix-relative path, rule code)` — no line
  numbers. Baselined findings WARN; new fingerprints fail RED by set
  membership (a 1-for-1 swap fails). The baseline only shrinks automatically
  (`--fix` / `--shrink-baseline`); `--rebaseline` **proposes** — it prints the
  `config/gate_baseline.json` a developer would have to commit and writes
  nothing. Both gate config files are review-gated via
  `check_review_existence`.
  - **Corrected 2026-08-08 — this bullet used to say "`--rebaseline` is a
    developer-consent action the agent must never run autonomously".** That was
    a rule addressed to the actor it was meant to bind, and the code did not
    back it: `main()` called `_write_baseline(current_fps)` the moment the flag
    appeared. Do not restate the old wording; it is the exact pattern the next
    section is about. Note the file has never existed in this template or in any
    of the four derived projects (measured 2026-08-08:
    `ls config/gate_baseline.json` → absent in all five), so no *recorded debt*
    has ever been compared against.
  - **Second correction, same day: "no baseline file" ≠ "the comparison never
    runs".** Three write-ups said it did not; measured, `--rebaseline` on a repo
    with no baseline file routes format *and* lint through
    `_check_against_baseline` against an empty set, reporting every finding as
    "N NEW finding(s) not in baseline" when no baseline exists. Verdict is the
    same RED, wording is a wart. Pinned at the CLI by
    `TestWhichPathRunsWhenNoBaselineFileExists`. **The transferable habit:** when
    you write "X never runs", spy on X in a CLI test rather than reasoning about
    the guard condition — the reasoning had covered the ordinary run and silently
    generalised.

## A guarantee about `main()` needs a test of `main()`

The single most expensive testing mistake in this repo's record, worth stating
as a rule because it has now happened twice on the same mechanism:

> **A property asserted in a docstring and covered only by a unit test of a
> pure helper is not covered. If the claim names the CLI, the test must drive
> the CLI.**

The case. `scripts/quality_gate.py` claims *"no invocation of this script — no
flag, no combination of flags — can add a fingerprint to
config/gate_baseline.json"*. The fix that made it true also **deleted** the only
test that drove `--rebaseline` end-to-end through `main()` and replaced it with
unit tests on the pure decision function `_baseline_write_plan`. The helper
tests were good tests — they pin all 8 flag combinations — but the guarantee is
about `main()`, and after the swap `grep -n '"--rebaseline"' tests/*.py`
returned **nothing**. A reviewer restored the literal pre-fix defect
(`_write_baseline(current_fps)` back in `main()`) and measured the suite:
**163 passed, exit 0**. The guard had moved out of a test and into prose.

What to do instead — both, not either:

1. Keep the helper tests. They cover the combinatorics one end-to-end run
   cannot.
2. Add at least one **CLI-level** test per guaranteed outcome, driving real
   `argv` through `main()` in a `tmp_path` sandbox (repoint the module's path
   globals with `monkeypatch.setattr` so a reintroduced write lands in tmp,
   never in the repo).
3. **Prove the CLI test can fail**: apply the defect in a *scratch copy of the
   tree* and watch it go red. Never mutate the repo to test a mutation.
4. Give every such test a **non-vacuity assertion** — something that proves the
   branch actually executed (a printed line, a log field). "No file was
   written" passes trivially if the code path never ran.

Live example to copy, in `tests/test_quality_gate.py`:
`TestRebaselineWritesNothingThroughMain` (3 tests / 6 cases, CLI-level) sitting
alongside `TestBaselineCannotGrow` (the helper tests) — neither replaces the
other. Measured 2026-08-08 against a **173**-passing scratch copy: with the
defect restored in `main()`, **7 tests fail**, 166 pass; deselect the CLI class
and **1 still fails** (166 pass), because
`TestWhichPathRunsWhenNoBaselineFileExists` independently asserts no baseline
file is created.

That last number replaced an earlier "165 pass, exit 0 — nothing else notices",
and the replacement is worth more than the correction: **the count of tests that
catch a mutation is itself a measurement with a shelf life.** Re-run the mutation
before quoting the figure; do not inherit it.

### Corollary: name the guarantee precisely, then test *that*

While writing the CLI tests above, a second mutation exposed a subtler version
of the same failure. The mechanism makes **two** promises — "cannot GROW the
baseline" and "writes NOTHING" — and deleting the `--rebaseline` veto from the
helper breaks only the second: the write falls through to a *subset* of the
existing baseline, so the growth invariant still holds. The whole suite stayed
green, because the existing helper test only ever passed a `current` containing
new debt, where the result is `None` for an unrelated reason.

**A test can be about the right thing and still pass for the wrong reason.** Two
habits catch it:

- **Vary the input so the guard under test is the only thing producing the
  result.** Parametrize over the states where the *other* early-returns do not
  fire.
- **Assert the strongest promise you actually make.** "The file did not grow" is
  weaker than "the file is byte-identical". If the docstring says *writes
  nothing*, assert bytes.

*A test that stays green when you break the thing it guards is not evidence.*
