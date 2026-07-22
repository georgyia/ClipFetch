"""Read-only topic endpoints: list topics, one topic, and a topic's clips."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from clipfetch.api.dependencies import ActiveLibraryRootDep
from clipfetch.api.errors import ApiException
from clipfetch.services import topic_service
from clipfetch.services.catalog_service import InvalidCursorError
from clipfetch.topics import TopicError

router = APIRouter(prefix="/api/v1/topics", tags=["topics"])

_SORTS = {"date", "likes", "views", "author"}


@router.get("")
def list_topics(root: ActiveLibraryRootDep) -> dict[str, Any]:
    try:
        topics = topic_service.list_topics(root)
    except TopicError:
        # A library with no topics configured is an empty channel list, not an error.
        return {"topics": []}
    return {"topics": [item.to_dict() for item in topics]}


@router.get("/{slug}")
def get_topic(slug: str, root: ActiveLibraryRootDep) -> dict[str, Any]:
    try:
        return topic_service.get_topic(root, slug).to_dict()
    except TopicError as err:
        raise ApiException(404, "topic_not_found", str(err)) from err


@router.get("/{slug}/clips")
def list_topic_clips(
    slug: str,
    root: ActiveLibraryRootDep,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 24,
    sort: Annotated[str, Query()] = "date",
) -> dict[str, Any]:
    if sort not in _SORTS:
        raise ApiException(422, "invalid_sort", f"sort must be one of: {', '.join(sorted(_SORTS))}")
    try:
        page = topic_service.list_topic_clips(root, slug, sort=sort, cursor=cursor, limit=limit)
    except TopicError as err:
        raise ApiException(404, "topic_not_found", str(err)) from err
    except InvalidCursorError as err:
        raise ApiException(422, "invalid_cursor", str(err)) from err
    return page.to_dict()
