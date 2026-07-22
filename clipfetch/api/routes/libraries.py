"""Library registry endpoints: register, list, inspect, activate, unregister.

Registration never deletes anything and never returns a filesystem path. Unregistering removes only
the device-state registration, never the library's files or catalog.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from clipfetch.api.dependencies import AppStateDep
from clipfetch.api.errors import ApiException
from clipfetch.appstate import AppStateError
from clipfetch.services import library_service
from clipfetch.services.library_service import LibraryServiceError

router = APIRouter(prefix="/api/v1/libraries", tags=["libraries"])


class RegisterLibraryRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    path: str = Field(min_length=1)


@router.get("")
def list_libraries(appstate: AppStateDep) -> dict[str, Any]:
    return {"libraries": [item.to_dict() for item in library_service.list_libraries(appstate)]}


@router.post("", status_code=201)
def register_library(body: RegisterLibraryRequest, appstate: AppStateDep) -> dict[str, Any]:
    try:
        summary = library_service.register_library(appstate, body.display_name, body.path)
    except LibraryServiceError as err:
        raise ApiException(
            400, "invalid_library", str(err), recovery_actions=("choose_directory",)
        ) from err
    return summary.to_dict()


@router.get("/{library_id}")
def get_library(library_id: str, appstate: AppStateDep) -> dict[str, Any]:
    try:
        return library_service.get_library(appstate, library_id).to_dict()
    except AppStateError as err:
        raise ApiException(404, "library_not_found", str(err)) from err


@router.post("/{library_id}/activate")
def activate_library(library_id: str, appstate: AppStateDep) -> dict[str, Any]:
    try:
        return library_service.activate_library(appstate, library_id).to_dict()
    except AppStateError as err:
        raise ApiException(404, "library_not_found", str(err)) from err


@router.delete("/{library_id}", status_code=204)
def unregister_library(library_id: str, appstate: AppStateDep) -> Response:
    try:
        library_service.unregister_library(appstate, library_id)
    except AppStateError as err:
        raise ApiException(404, "library_not_found", str(err)) from err
    return Response(status_code=204)
