"""FastAPI Todo application — test project for the Agentic Development Framework."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import TodoDatabase
from .routes import router, set_database

db = TodoDatabase()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    db.connect()
    set_database(db)
    yield
    db.close()


app = FastAPI(
    title="Todo API",
    description="Minimal Todo API for testing the Agentic Development Framework",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)
