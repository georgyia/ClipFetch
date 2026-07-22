"""FastAPI application factory for ClipFetch Watch.

Serves health probes, an optional-capability matrix, and (in later issues) the product API beneath
``/api/v1``. Loopback-only usage is assumed: no CORS is enabled and responses carry a request id and
conservative headers.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from clipfetch import __version__
from clipfetch.api.capabilities import capability_matrix
from clipfetch.api.errors import install_exception_handlers

API_PREFIX = "/api/v1"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request id to every request/response and set conservative headers."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response


def create_app() -> FastAPI:
    """Build the ClipFetch Watch API application."""
    app = FastAPI(
        title="ClipFetch Watch API",
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(RequestContextMiddleware)
    install_exception_handlers(app)

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready() -> dict[str, str]:
        return {"status": "ready"}

    @app.get(f"{API_PREFIX}/capabilities")
    def capabilities() -> dict[str, Any]:
        return {"capabilities": capability_matrix()}

    return app
