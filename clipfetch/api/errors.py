"""Safe error envelope and exception handlers for the API.

Every error leaves the process as the stable :class:`clipfetch.contracts.ApiError` envelope with a
machine code, a user-safe message, and the request id. Python exceptions are never serialized
directly, so internal messages, paths, and stack traces never reach a client.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from clipfetch.contracts import ApiError

# Map common HTTP statuses to stable machine codes for the envelope.
_STATUS_CODES = {
    400: "bad_request",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "invalid_request",
}


class ApiException(Exception):
    """A deliberate, client-safe API error with an HTTP status and a stable code."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        recovery_actions: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.recovery_actions = recovery_actions


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _envelope(request: Request, status: int, code: str, message: str, actions=()) -> JSONResponse:
    error = ApiError(
        code=code, message=message, request_id=_request_id(request), recovery_actions=actions
    )
    return JSONResponse(status_code=status, content=error.to_dict())


def install_exception_handlers(app: FastAPI) -> None:
    """Register handlers that render every failure as a sanitized error envelope."""

    async def handle_api_exception(request: Request, exc: ApiException) -> JSONResponse:
        return _envelope(request, exc.status_code, exc.code, exc.message, exc.recovery_actions)

    async def handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _envelope(request, 422, "invalid_request", "The request parameters are invalid.")

    async def handle_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "http_error")
        default = "The request could not be completed."
        message = exc.detail if isinstance(exc.detail, str) else default
        return _envelope(request, exc.status_code, code, message)

    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        return _envelope(request, 500, "internal_error", "An unexpected internal error occurred.")

    app.add_exception_handler(ApiException, handle_api_exception)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, handle_validation)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, handle_http)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, handle_unexpected)
