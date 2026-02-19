"""Shared test fixtures for the Todo API."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.database import TodoDatabase
from src.main import app
from src.routes import set_database


@pytest.fixture
async def test_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test_todo.db"
    db = TodoDatabase(db_path)
    db.connect()
    set_database(db)
    yield db
    db.close()


@pytest.fixture
async def client(test_db):
    """Create an async test client with a clean database."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def sample_todo(client):
    """Create a sample todo and return the response data."""
    response = await client.post(
        "/todos", json={"title": "Test Todo", "description": "A test todo item"}
    )
    return response.json()
