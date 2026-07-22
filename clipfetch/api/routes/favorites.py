"""Favorites endpoints for the active library.

Toggle a clip's favorite state and list favorited clips. State is device-local and scoped to the
active library. Listing returns the same public clip summaries as every other clip view.

FastAPI evaluates these route signatures at runtime, so this module intentionally does not use
``from __future__ import annotations`` and uses ``Optional[...]`` for Python 3.9 compatibility.
"""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Response

from clipfetch.api.dependencies import ActiveLibraryDep, AppStateDep
from clipfetch.services import favorites_service

router = APIRouter(prefix="/api/v1", tags=["favorites"])


@router.get("/favorites")
def list_favorites(appstate: AppStateDep, library: ActiveLibraryDep) -> dict[str, Any]:
    page = favorites_service.list_favorites(Path(library.root_path), appstate, library.id)
    return page.to_dict()


@router.get("/clips/{clip_id}/favorite")
def get_favorite(
    clip_id: str, appstate: AppStateDep, library: ActiveLibraryDep
) -> dict[str, Any]:
    return {"favorite": favorites_service.is_favorite(appstate, library.id, clip_id)}


@router.put("/clips/{clip_id}/favorite")
def add_favorite(
    clip_id: str, appstate: AppStateDep, library: ActiveLibraryDep
) -> dict[str, Any]:
    favorites_service.set_favorite(appstate, library.id, clip_id, True)
    return {"favorite": True}


@router.delete("/clips/{clip_id}/favorite")
def remove_favorite(
    clip_id: str, appstate: AppStateDep, library: ActiveLibraryDep
) -> Response:
    favorites_service.set_favorite(appstate, library.id, clip_id, False)
    return Response(status_code=204)
