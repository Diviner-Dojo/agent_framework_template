"""Shared test fixtures for the Todo API."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.database import TodoDatabase
from src.main import app
from src.routes import set_database


def pytest_addoption(parser):
    """Register custom CLI options for gated test markers."""
    parser.addoption(
        "--run-llm",
        action="store_true",
        default=False,
        help="Run tests marked with 'uses_llm' (skipped by default — these call real LLM APIs)",
    )
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="Run tests marked with 'slow' (skipped by default)",
    )


def pytest_collection_modifyitems(config, items):
    """Skip LLM and slow tests unless their CLI flag is provided."""
    if not config.getoption("--run-llm"):
        skip_llm = pytest.mark.skip(reason="need --run-llm option to run")
        for item in items:
            if "uses_llm" in item.keywords:
                item.add_marker(skip_llm)
    if not config.getoption("--run-slow"):
        skip_slow = pytest.mark.skip(reason="need --run-slow option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)


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
