"""Library maintenance endpoints: find clips whose media is gone, and forget their records.

FastAPI evaluates these route signatures at runtime, so this module intentionally does not use
``from __future__ import annotations`` and uses ``Optional[...]`` for Python 3.9 compatibility.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from clipfetch.api.dependencies import ActiveLibraryRootDep
from clipfetch.api.errors import ApiException
from clipfetch.catalog import CatalogError
from clipfetch.services import maintenance_service

router = APIRouter(prefix="/api/v1/maintenance", tags=["maintenance"])

#: A forget request is a person clearing a triage list, so this is generous but bounded.
MAX_FORGET_PER_REQUEST = 500


class ForgetRequest(BaseModel):
    clip_ids: list[str] = Field(min_length=1, max_length=MAX_FORGET_PER_REQUEST)


@router.get("/missing")
def list_missing(
    root: ActiveLibraryRootDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """Clips the catalog knows about whose media file is not on disk."""
    try:
        return maintenance_service.list_missing(root, limit=limit, offset=offset).to_dict()
    except CatalogError as err:
        raise ApiException(404, "library_unavailable", str(err)) from err


@router.post("/missing/forget")
def forget_missing(body: ForgetRequest, root: ActiveLibraryRootDep) -> dict[str, Any]:
    """Drop catalog records for clips whose media is gone. Never deletes a file.

    A clip whose file turns out to be present is reported back under ``kept`` rather than removed,
    so a stale list cannot become a delete button.
    """
    try:
        report = maintenance_service.forget_clips(root, body.clip_ids)
    except CatalogError as err:
        raise ApiException(404, "library_unavailable", str(err)) from err
    return report.to_dict()
