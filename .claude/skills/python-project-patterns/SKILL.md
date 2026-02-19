---
name: python-project-patterns
description: "Python project patterns and best practices for FastAPI applications. Reference when writing or reviewing Python code."
---

# Python Project Patterns

## FastAPI Application Structure

### App Factory Pattern
```python
from fastapi import FastAPI

def create_app() -> FastAPI:
    app = FastAPI(title="Project Name", version="1.0.0")
    app.include_router(router, prefix="/api")
    return app
```

### Lifespan for Startup/Shutdown
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize DB, connections
    await init_db()
    yield
    # Shutdown: cleanup
    await close_db()
```

### Dependency Injection
```python
from fastapi import Depends

def get_db() -> Database:
    db = Database()
    try:
        yield db
    finally:
        db.close()

@router.get("/items")
async def list_items(db: Database = Depends(get_db)):
    return db.get_all()
```

## Pydantic Models

### Request/Response Separation
- Create models: `ItemCreate` (input), `ItemUpdate` (partial input), `ItemResponse` (output)
- Input models validate and constrain; output models shape the response
- Use `model_config = ConfigDict(from_attributes=True)` for ORM integration

### Validation
```python
from pydantic import BaseModel, Field

class TodoCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=1000)
```

## Error Handling

### HTTP Exception Pattern
```python
from fastapi import HTTPException

@router.get("/items/{item_id}")
async def get_item(item_id: int):
    item = db.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
```

### Custom Exception Handlers
Register at the app level for consistent error responses across all endpoints.

## Project Layout
```
src/
  __init__.py
  main.py          # App creation and configuration
  models.py         # Pydantic models
  routes.py         # API endpoints
  database.py       # Data access layer
  dependencies.py   # Shared dependencies (if needed)
tests/
  conftest.py       # Shared fixtures
  test_routes.py    # Endpoint tests
```
