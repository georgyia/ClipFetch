"""Bootstrap endpoint: everything the shell needs on first paint, in one request."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from clipfetch import __version__
from clipfetch.api.capabilities import capability_matrix
from clipfetch.api.dependencies import AppStateDep
from clipfetch.services import library_service

router = APIRouter(prefix="/api/v1", tags=["bootstrap"])


@router.get("/bootstrap")
def bootstrap(appstate: AppStateDep) -> dict[str, Any]:
    active = library_service.active_library(appstate)
    return {
        "app_version": __version__,
        "active_library": active.to_dict() if active is not None else None,
        "libraries": [item.to_dict() for item in library_service.list_libraries(appstate)],
        "capabilities": capability_matrix(),
        "worker": {"state": "not_configured"},
    }
