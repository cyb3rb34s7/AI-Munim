"""Domain errors and the global FastAPI exception handlers.

Per docs/conventions.md §10.1: NO broad `except Exception:`. Module code should
either catch the specific class it understands and re-raise a typed MunimError,
or let the exception propagate to these handlers - which is the single place
that converts any exception into the standard error envelope.

Per docs/conventions.md §4.2: every error response carries `code`, `message`,
optional `details`, and the `trace_id` from `request.state` (set by the
TraceIdMiddleware).
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from munim.shared.constants import ErrorCode
from munim.shared.logging import get_logger
from munim.shared.responses import build_error_envelope

log = get_logger("munim.errors")


class MunimError(Exception):
    """Base class for every domain error. Subclasses set `code`, `http_status`, `message`."""

    code: str = ErrorCode.SYSTEM_UNEXPECTED.value
    http_status: int = 500
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message or self.message)
        if message is not None:
            self.message = message
        self.details = details


class ValidationFailedError(MunimError):
    code = ErrorCode.VALIDATION_BAD_FORMAT.value
    http_status = 422
    message = "Validation failed."


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(MunimError)
    async def _munim_error_handler(request: Request, exc: MunimError) -> JSONResponse:
        log.warning(
            "error.domain",
            code=exc.code,
            status=exc.http_status,
            details=exc.details,
        )
        return JSONResponse(
            status_code=exc.http_status,
            content=build_error_envelope(
                code=exc.code,
                message=exc.message,
                details=exc.details,
                trace_id=request.state.trace_id,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        log.warning("error.validation", errors=exc.errors())
        return JSONResponse(
            status_code=422,
            content=build_error_envelope(
                code=ErrorCode.VALIDATION_BAD_FORMAT.value,
                message="Request validation failed.",
                details={"errors": exc.errors()},
                trace_id=request.state.trace_id,
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_envelope(
                code=f"http.{exc.status_code}",
                message=str(exc.detail) if exc.detail else "HTTP error.",
                details=None,
                trace_id=request.state.trace_id,
            ),
        )

    @app.exception_handler(Exception)
    async def _unexpected_handler(request: Request, exc: Exception) -> JSONResponse:
        log.exception("error.unexpected", exc_type=type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content=build_error_envelope(
                code=ErrorCode.SYSTEM_UNEXPECTED.value,
                message="An unexpected error occurred.",
                details=None,
                trace_id=request.state.trace_id,
            ),
        )
