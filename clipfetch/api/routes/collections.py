"""Read-only collection endpoints: list collections, one collection, and its clips.

Collection creation and deletion are a separate mutation issue; this module is read-only.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from clipfetch.api.dependencies import ActiveLibraryRootDep
from clipfetch.api.errors import ApiException
from clipfetch.collections import CollectionError
from clipfetch.services import collection_service
from clipfetch.services.catalog_service import InvalidCursorError

router = APIRouter(prefix="/api/v1/collections", tags=["collections"])

_SORTS = {"date", "likes", "views", "author"}


@router.get("")
def list_collections(root: ActiveLibraryRootDep) -> dict[str, Any]:
    try:
        collections = collection_service.list_collections(root)
    except CollectionError as err:
        raise ApiException(422, "invalid_collections", str(err)) from err
    return {"collections": [item.to_dict() for item in collections]}


@router.get("/{collection_id}")
def get_collection(collection_id: str, root: ActiveLibraryRootDep) -> dict[str, Any]:
    try:
        return collection_service.get_collection_summary(root, collection_id).to_dict()
    except CollectionError as err:
        raise ApiException(404, "collection_not_found", str(err)) from err


@router.get("/{collection_id}/clips")
def list_collection_clips(
    collection_id: str,
    root: ActiveLibraryRootDep,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 24,
    sort: Annotated[str, Query()] = "date",
) -> dict[str, Any]:
    if sort not in _SORTS:
        raise ApiException(422, "invalid_sort", f"sort must be one of: {', '.join(sorted(_SORTS))}")
    try:
        page = collection_service.list_collection_clips(
            root, collection_id, sort=sort, cursor=cursor, limit=limit
        )
    except CollectionError as err:
        raise ApiException(404, "collection_not_found", str(err)) from err
    except InvalidCursorError as err:
        raise ApiException(422, "invalid_cursor", str(err)) from err
    return page.to_dict()
