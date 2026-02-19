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
