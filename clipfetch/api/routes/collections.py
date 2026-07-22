"""Collection endpoints: list, inspect, browse, and manage saved dynamic collections.

Collections are stored filter definitions, never materialized clip lists; mutations reuse the same
validators as the CLI. FastAPI evaluates these route signatures at runtime, so this module
intentionally does not use ``from __future__ import annotations`` and uses ``Optional[...]`` for
Python 3.9 compatibility.
"""

from datetime import date
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, Field

from clipfetch.api.dependencies import ActiveLibraryRootDep
from clipfetch.api.errors import ApiException
from clipfetch.collections import CollectionError
from clipfetch.library import ClipFilter
from clipfetch.services import collection_service
from clipfetch.services.catalog_service import InvalidCursorError

router = APIRouter(prefix="/api/v1/collections", tags=["collections"])

_SORTS = {"date", "likes", "views", "author"}


class CollectionFilters(BaseModel):
    """The subset of the clip filter allowlist that a collection can pin. All fields optional."""

    min_likes: Optional[int] = Field(default=None, ge=0)
    max_likes: Optional[int] = Field(default=None, ge=0)
    min_views: Optional[int] = Field(default=None, ge=0)
    max_views: Optional[int] = Field(default=None, ge=0)
    authors: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    downloaded_after: Optional[date] = None
    downloaded_before: Optional[date] = None

    def to_clip_filter(self) -> ClipFilter:
        return ClipFilter(
            min_likes=self.min_likes,
            max_likes=self.max_likes,
            min_views=self.min_views,
            max_views=self.max_views,
            authors=tuple(self.authors),
            hashtags=tuple(self.hashtags),
            platforms=tuple(self.platforms),
            topics=tuple(self.topics),
            downloaded_after=self.downloaded_after,
            downloaded_before=self.downloaded_before,
        )


class CreateCollectionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    filters: CollectionFilters = Field(default_factory=CollectionFilters)


class UpdateCollectionRequest(BaseModel):
    filters: CollectionFilters


@router.get("")
def list_collections(root: ActiveLibraryRootDep) -> dict[str, Any]:
    try:
        collections = collection_service.list_collections(root)
    except CollectionError as err:
        raise ApiException(422, "invalid_collections", str(err)) from err
    return {"collections": [item.to_dict() for item in collections]}


@router.post("", status_code=201)
def create_collection(body: CreateCollectionRequest, root: ActiveLibraryRootDep) -> dict[str, Any]:
    try:
        summary = collection_service.create_collection(
            root, body.name, body.filters.to_clip_filter()
        )
    except CollectionError as err:
        raise ApiException(422, "invalid_collection", str(err)) from err
    return summary.to_dict()


@router.get("/{collection_id}")
def get_collection(collection_id: str, root: ActiveLibraryRootDep) -> dict[str, Any]:
    try:
        return collection_service.get_collection_summary(root, collection_id).to_dict()
    except CollectionError as err:
        raise ApiException(404, "collection_not_found", str(err)) from err


@router.put("/{collection_id}")
def update_collection(
    collection_id: str, body: UpdateCollectionRequest, root: ActiveLibraryRootDep
) -> dict[str, Any]:
    try:
        summary = collection_service.update_collection(
            root, collection_id, body.filters.to_clip_filter()
        )
    except CollectionError as err:
        raise ApiException(404, "collection_not_found", str(err)) from err
    return summary.to_dict()


@router.delete("/{collection_id}", status_code=204)
def delete_collection(collection_id: str, root: ActiveLibraryRootDep) -> Response:
    try:
        collection_service.delete_collection(root, collection_id)
    except CollectionError as err:
        raise ApiException(404, "collection_not_found", str(err)) from err
    return Response(status_code=204)


@router.get("/{collection_id}/clips")
def list_collection_clips(
    collection_id: str,
    root: ActiveLibraryRootDep,
    cursor: Annotated[Optional[str], Query()] = None,
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
