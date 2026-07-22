"""Read-only clip endpoints: cursor-paginated listing with a filter allowlist, and clip detail.

FastAPI evaluates these route signatures at runtime, so this module intentionally does not use
``from __future__ import annotations`` and uses ``Optional[...]`` for Python 3.9 compatibility.
"""

from datetime import date
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Query

from clipfetch.api.dependencies import ActiveLibraryRootDep
from clipfetch.api.errors import ApiException
from clipfetch.catalog import CatalogError
from clipfetch.library import ClipFilter
from clipfetch.services import catalog_service
from clipfetch.services.catalog_service import InvalidCursorError

router = APIRouter(prefix="/api/v1/clips", tags=["clips"])

# Only these sorts are accepted; anything else is a client error, not a 500.
_SORTS = {"date", "likes", "views", "author"}


def _require_sort(sort: str) -> None:
    if sort not in _SORTS:
        raise ApiException(
            422, "invalid_sort", f"sort must be one of: {', '.join(sorted(_SORTS))}"
        )


@router.get("")
def list_clips(
    root: ActiveLibraryRootDep,
    cursor: Annotated[Optional[str], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 24,
    sort: Annotated[str, Query()] = "date",
    topic: Annotated[Optional[list[str]], Query()] = None,
    creator: Annotated[Optional[list[str]], Query()] = None,
    hashtag: Annotated[Optional[list[str]], Query()] = None,
    platform: Annotated[Optional[list[str]], Query()] = None,
    min_likes: Annotated[Optional[int], Query(ge=0)] = None,
    max_likes: Annotated[Optional[int], Query(ge=0)] = None,
    min_views: Annotated[Optional[int], Query(ge=0)] = None,
    max_views: Annotated[Optional[int], Query(ge=0)] = None,
    downloaded_after: Annotated[Optional[date], Query()] = None,
    downloaded_before: Annotated[Optional[date], Query()] = None,
) -> dict[str, Any]:
    _require_sort(sort)
    filters = ClipFilter(
        min_likes=min_likes,
        max_likes=max_likes,
        min_views=min_views,
        max_views=max_views,
        authors=tuple(creator or ()),
        hashtags=tuple(hashtag or ()),
        platforms=tuple(platform or ()),
        topics=tuple(topic or ()),
        downloaded_after=downloaded_after,
        downloaded_before=downloaded_before,
    )
    try:
        page = catalog_service.list_clips(root, filters, sort=sort, cursor=cursor, limit=limit)
    except InvalidCursorError as err:
        raise ApiException(422, "invalid_cursor", str(err)) from err
    except CatalogError as err:
        raise ApiException(404, "library_unavailable", str(err)) from err
    return page.to_dict()


@router.get("/{clip_id}")
def get_clip(clip_id: str, root: ActiveLibraryRootDep) -> dict[str, Any]:
    try:
        return catalog_service.get_clip(root, clip_id).to_dict()
    except CatalogError as err:
        raise ApiException(
            404, "clip_not_found", str(err), recovery_actions=("open_library",)
        ) from err
