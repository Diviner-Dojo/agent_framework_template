"""Centralized error handling for the FastAPI application.

Registers two exception handlers:
1. AppError → structured JSON with error_code and details
2. Exception → generic 500 that never leaks stack traces

Call setup_error_handlers(app) during application startup.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .exceptions import AppError

logger = logging.getLogger(__name__)


def setup_error_handlers(app: FastAPI) -> None:
    """Register centralized exception handlers on the FastAPI app."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        """Handle known application errors with structured responses."""
        logger.warning("%s: %s (details=%s)", exc.error_code, exc.message, exc.details)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.message,
                "error_code": exc.error_code,
                **exc.details,
            },
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all for unhandled exceptions. Never exposes internals."""
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "error_code": "INTERNAL_ERROR",
            },
        )
