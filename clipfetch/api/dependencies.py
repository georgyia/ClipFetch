"""Shared FastAPI dependencies.

These resolve process-wide handles (the application-state database) and the active library,
translating missing state into safe API errors rather than raw exceptions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import Depends, Request

from clipfetch.api.errors import ApiException
from clipfetch.appstate import AppState
from clipfetch.services import library_service


def get_appstate(request: Request) -> AppState:
    appstate = getattr(request.app.state, "appstate", None)
    if appstate is None:  # pragma: no cover - misconfiguration guard
        raise ApiException(503, "appstate_unavailable", "Application state is not available.")
    return appstate


AppStateDep = Annotated[AppState, Depends(get_appstate)]


def get_active_library_root(appstate: AppStateDep) -> Path:
    root = library_service.active_library_root(appstate)
    if root is None:
        raise ApiException(
            409,
            "no_active_library",
            "No library is active. Register and activate a library first.",
            recovery_actions=("activate_library",),
        )
    return root


ActiveLibraryRootDep = Annotated[Path, Depends(get_active_library_root)]
