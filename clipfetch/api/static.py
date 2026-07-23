"""One-origin static serving for the ClipFetch Watch UI bundle.

In development the UI runs on Vite and proxies ``/api`` + ``/health`` to this server (two ports). In
production ``clipfetch web`` serves everything from a single origin: the API under its routers and
the built single-page app for everything else. The bundle is optional — when it is absent the server
runs API-only and says so, rather than failing — so a source checkout still works before a UI build.

The SPA is served as a *fallback on genuine 404s* (see :func:`spa_fallback_response`, wired into the
HTTP error handler) rather than a catch-all route, so it can never shadow an API route: real routes
are matched first, and only an unmatched GET for a non-API path resolves to the app shell. That
makes deep links and refreshes load the app while ``/api`` and ``/health`` 404s stay JSON.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.responses import FileResponse

#: The packaged bundle location; overridable for tests or a custom build.
_DEFAULT_BUNDLE_DIR = Path(__file__).resolve().parent.parent / "webui"
_ENV_OVERRIDE = "CLIPFETCH_WEBUI_DIR"

# Paths owned by the API — the SPA fallback must never answer these.
_RESERVED_PREFIXES = ("api/", "health/")


def bundle_dir() -> Path | None:
    """Return the UI bundle directory if it holds a built ``index.html``, else ``None``."""
    override = os.environ.get(_ENV_OVERRIDE)
    root = Path(override) if override else _DEFAULT_BUNDLE_DIR
    return root if (root / "index.html").is_file() else None


def mount_frontend(app: FastAPI) -> bool:
    """Mount the hashed asset directory if a bundle is present. Returns whether it was mounted.

    Everything else (``/``, client-side routes, root files) is served by
    :func:`spa_fallback_response` from the 404 handler, so no route here can shadow the API.
    """
    bundle = bundle_dir()
    if bundle is None:
        return False
    assets = bundle / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")
    return True


def spa_fallback_response(request: Request) -> FileResponse | None:
    """For an unmatched GET outside the API, return a bundled file or the SPA shell; else ``None``.

    Called only on a 404 so it never shadows a real route. Returns ``None`` for API/health paths and
    non-GET requests so those keep their JSON error envelope.
    """
    bundle = bundle_dir()
    if bundle is None or request.method not in ("GET", "HEAD"):
        return None
    path = request.url.path.lstrip("/")
    if path.startswith(_RESERVED_PREFIXES):
        return None
    file = _safe_file(bundle, path)
    if file is not None:
        return FileResponse(file)  # a real root asset (favicon, manifest, …)
    return FileResponse(bundle / "index.html")  # deep link / refresh → app shell


def _safe_file(bundle: Path, path: str) -> Path | None:
    """Return a real file inside ``bundle`` for ``path``, or ``None`` (SPA fallback / traversal)."""
    if not path:
        return None
    try:
        candidate = (bundle / path).resolve()
        candidate.relative_to(bundle.resolve())
    except (ValueError, OSError):
        return None
    return candidate if candidate.is_file() else None
