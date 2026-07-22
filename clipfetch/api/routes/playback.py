"""Playback progress endpoints for the active library.

Read and write per-clip playback position so the browser can resume where it left off and the home
screen can compose a Continue Watching rail. State is device-local and scoped to the active library.

FastAPI evaluates these route signatures at runtime, so this module intentionally does not use
``from __future__ import annotations`` and uses ``Optional[...]`` for Python 3.9 compatibility.
"""

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from clipfetch.api.dependencies import ActiveLibraryDep, AppStateDep
from clipfetch.api.errors import ApiException
from clipfetch.appstate import AppStateError
from clipfetch.services import playback_service

router = APIRouter(prefix="/api/v1/clips", tags=["playback"])


class PlaybackWriteRequest(BaseModel):
    position_ms: int = Field(ge=0)
    duration_ms: Optional[int] = Field(default=None, ge=0)
    completed: Optional[bool] = None


@router.get("/{clip_id}/playback")
def get_playback(
    clip_id: str, appstate: AppStateDep, library: ActiveLibraryDep
) -> dict[str, Any]:
    view = playback_service.get_playback(appstate, library.id, clip_id)
    return {"playback": view.to_dict() if view is not None else None}


@router.put("/{clip_id}/playback")
def put_playback(
    clip_id: str, body: PlaybackWriteRequest, appstate: AppStateDep, library: ActiveLibraryDep
) -> dict[str, Any]:
    try:
        view = playback_service.save_playback(
            appstate,
            library.id,
            clip_id,
            position_ms=body.position_ms,
            duration_ms=body.duration_ms,
            completed=body.completed,
        )
    except AppStateError as err:
        raise ApiException(422, "invalid_playback", str(err)) from err
    return {"playback": view.to_dict()}
