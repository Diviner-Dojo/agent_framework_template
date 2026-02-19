"""Pydantic models for the Todo API."""

from datetime import datetime

from pydantic import BaseModel, Field


class TodoCreate(BaseModel):
    """Request model for creating a new todo."""

    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=1000)


class TodoUpdate(BaseModel):
    """Request model for updating an existing todo."""

    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=1000)
    completed: bool | None = None


class TodoResponse(BaseModel):
    """Response model for a todo item."""

    id: int
    title: str
    description: str | None
    completed: bool
    created_at: str
