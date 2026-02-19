"""API routes for the Todo API."""

from fastapi import APIRouter, Query

from .exceptions import NotFoundError
from .models import TodoCreate, TodoResponse, TodoUpdate

router = APIRouter()

# Database instance is set during app startup (see main.py)
_db = None


def set_database(db):
    """Set the database instance for routes. Called during app startup."""
    global _db
    _db = db


def get_db():
    """Get the current database instance."""
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db


@router.get("/todos", response_model=list[TodoResponse])
async def list_todos(completed: bool | None = Query(None)):
    """List all todos, optionally filtered by completion status."""
    return get_db().list_todos(completed=completed)


@router.post("/todos", response_model=TodoResponse, status_code=201)
async def create_todo(todo: TodoCreate):
    """Create a new todo item."""
    return get_db().create_todo(title=todo.title, description=todo.description)


@router.get("/todos/{todo_id}", response_model=TodoResponse)
async def get_todo(todo_id: int):
    """Get a specific todo by ID."""
    todo = get_db().get_todo(todo_id)
    if todo is None:
        raise NotFoundError("todo", todo_id)
    return todo


@router.patch("/todos/{todo_id}", response_model=TodoResponse)
async def update_todo(todo_id: int, update: TodoUpdate):
    """Update a todo item. Only provided fields are changed."""
    todo = get_db().update_todo(
        todo_id,
        title=update.title,
        description=update.description,
        completed=update.completed,
    )
    if todo is None:
        raise NotFoundError("todo", todo_id)
    return todo


@router.delete("/todos/{todo_id}", status_code=204)
async def delete_todo(todo_id: int):
    """Delete a todo item."""
    deleted = get_db().delete_todo(todo_id)
    if not deleted:
        raise NotFoundError("todo", todo_id)
