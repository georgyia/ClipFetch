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
from clipfetch.api.routes import (
    bootstrap,
    clips,
    collections,
    favorites,
    home,
    libraries,
    media,
    playback,
    search,
    topics,
)
from clipfetch.appstate import AppState

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


def create_app(appstate: AppState | None = None) -> FastAPI:
    """Build the ClipFetch Watch API application.

    ``appstate`` may be supplied (tests, custom locations); otherwise the OS-default
    application-state database is opened lazily.
    """
    app = FastAPI(
        title="ClipFetch Watch API",
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.appstate = appstate if appstate is not None else AppState.open()
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

    app.include_router(bootstrap.router)
    app.include_router(libraries.router)
    app.include_router(clips.router)
    app.include_router(topics.router)
    app.include_router(collections.router)
    app.include_router(favorites.router)
    app.include_router(home.router)
    app.include_router(media.router)
    app.include_router(playback.router)
    app.include_router(search.router)
    return app
