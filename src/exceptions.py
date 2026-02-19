"""Application exception hierarchy with structured error metadata.

All application-level errors inherit from AppError, which carries:
- message: Human-readable error description
- error_code: Machine-readable code for programmatic error handling
- details: Structured metadata dict (resource type, identifier, field, etc.)
- status_code: HTTP status code for the response

New projects extend this hierarchy with domain-specific subclasses.
The centralized error handler in error_handlers.py converts these
into consistent JSON responses automatically.
"""

from typing import Any


class AppError(Exception):
    """Base exception for all application errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "APP_ERROR",
        details: dict[str, Any] | None = None,
        status_code: int = 500,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.status_code = status_code


class NotFoundError(AppError):
    """Resource does not exist. Maps to HTTP 404."""

    def __init__(self, resource: str, identifier: str | int) -> None:
        super().__init__(
            message=f"{resource} not found: {identifier}",
            error_code="NOT_FOUND",
            details={"resource": resource, "identifier": str(identifier)},
            status_code=404,
        )


class ValidationError(AppError):
    """Business rule or input validation failure. Maps to HTTP 422."""

    def __init__(self, message: str, field: str | None = None) -> None:
        details: dict[str, Any] = {}
        if field is not None:
            details["field"] = field
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details=details,
            status_code=422,
        )


class ConflictError(AppError):
    """Duplicate or state conflict. Maps to HTTP 409."""

    def __init__(self, message: str, resource: str | None = None) -> None:
        details: dict[str, Any] = {}
        if resource is not None:
            details["resource"] = resource
        super().__init__(
            message=message,
            error_code="CONFLICT",
            details=details,
            status_code=409,
        )
