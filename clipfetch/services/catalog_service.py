"""Catalog query service: cursor-paginated clip listing and detail as public contracts.

This wraps the existing :func:`clipfetch.library.query_library` and
:func:`clipfetch.library.find_clip` so the CLI and the future API share one implementation of
listing, filtering, and detail. It adds two things the raw query layer does not: opaque cursor
pagination and conversion to the :mod:`clipfetch.contracts` DTOs (attaching each clip's assigned
topics). It deliberately does not add new filter behavior — that stays in
:class:`clipfetch.library.ClipFilter`.
"""

from __future__ import annotations

import base64
import binascii
from pathlib import Path

from clipfetch.catalog import Catalog, CatalogRecord
from clipfetch.contracts import ClipDetail, ClipPage, ClipSummary, clip_detail, clip_summary
from clipfetch.library import ClipFilter, find_clip, query_library

DEFAULT_LIMIT = 24
MAX_LIMIT = 100


class InvalidCursorError(ValueError):
    """A pagination cursor was malformed or out of range."""


def _encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode("ascii")).decode("ascii")


def _decode_cursor(cursor: str) -> int:
    try:
        offset = int(base64.urlsafe_b64decode(cursor.encode("ascii")).decode("ascii"))
    except (ValueError, binascii.Error, UnicodeError) as err:
        raise InvalidCursorError(f"invalid cursor: {cursor!r}") from err
    if offset < 0:
        raise InvalidCursorError("cursor offset must be non-negative")
    return offset


def _clamp_limit(limit: int) -> int:
    if limit < 1:
        return 1
    return min(limit, MAX_LIMIT)


def _topics_for(
    root: Path, clips: tuple[CatalogRecord, ...]
) -> dict[tuple[str, str], tuple[str, ...]]:
    if not clips:
        return {}
    with Catalog.open(root) as catalog:
        return {
            (record.platform, record.clip_id): catalog.topic_names(record.platform, record.clip_id)
            for record in clips
        }


def list_clips(
    root: Path,
    filters: ClipFilter | None = None,
    *,
    sort: str = "date",
    cursor: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> ClipPage:
    """Return one cursor-paginated page of clip summaries with assigned topics attached."""
    page_size = _clamp_limit(limit)
    offset = _decode_cursor(cursor) if cursor is not None else 0

    result = query_library(root, filters, sort=sort, limit=page_size, offset=offset)
    topics = _topics_for(root, result.clips)
    items = tuple(
        clip_summary(record, topics=topics.get((record.platform, record.clip_id), ()))
        for record in result.clips
    )

    next_offset = offset + len(items)
    next_cursor = _encode_cursor(next_offset) if next_offset < result.matched else None
    return ClipPage(items=items, next_cursor=next_cursor, total_matched=result.matched)


def get_clip(root: Path, clip_id: str) -> ClipDetail:
    """Return the full detail contract for one clip, or raise ``CatalogError`` if not found."""
    from clipfetch.services import quality_service

    record = find_clip(root, clip_id)
    with Catalog.open(root) as catalog:
        topics = catalog.topic_names(record.platform, record.clip_id)
        details = catalog.get_media_details(record.platform, record.clip_id)
    return clip_detail(record, topics=topics, media=quality_service.media_view(details))


__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "InvalidCursorError",
    "ClipPage",
    "ClipSummary",
    "ClipDetail",
    "list_clips",
    "get_clip",
]
