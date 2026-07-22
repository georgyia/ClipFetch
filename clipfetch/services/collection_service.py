"""Collection service: CRUD and browsing for saved dynamic collections.

Wraps :mod:`clipfetch.collections`, so the web layer and the CLI share the exact same validation and
query semantics — collections stay dynamic filter definitions, never materialized clip lists.
Browsing reuses :func:`clipfetch.services.catalog_service.list_clips` for pagination.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clipfetch.collections import (
    delete_collection as _delete_collection,
)
from clipfetch.collections import (
    filter_to_dict,
    get_collection,
    load_collections,
    save_collection,
)
from clipfetch.collections import (
    update_collection as _update_collection,
)
from clipfetch.contracts import ClipPage
from clipfetch.library import ClipFilter, query_library
from clipfetch.services.catalog_service import DEFAULT_LIMIT, list_clips


@dataclass(frozen=True)
class CollectionSummary:
    """A saved collection: its id, its dynamic filter definition, and its current match count."""

    id: str
    filters: dict[str, Any]
    clip_count: int

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "filters": self.filters, "clip_count": self.clip_count}


def _summary(root: Path, name: str, filters: ClipFilter) -> CollectionSummary:
    return CollectionSummary(
        id=name,
        filters=filter_to_dict(filters),
        clip_count=query_library(root, filters).matched,
    )


def list_collections(root: Path) -> tuple[CollectionSummary, ...]:
    """Return every saved collection with its current match count."""
    return tuple(_summary(root, item.name, item.filters) for item in load_collections(root))


def get_collection_summary(root: Path, name: str) -> CollectionSummary:
    """Return one collection summary, or raise ``CollectionError`` if it does not exist."""
    collection = get_collection(root, name)
    return _summary(root, collection.name, collection.filters)


def create_collection(root: Path, name: str, filters: ClipFilter) -> CollectionSummary:
    """Save a new collection through the shared validators and return its summary."""
    saved = save_collection(root, name, filters)
    return _summary(root, saved.name, saved.filters)


def update_collection(root: Path, name: str, filters: ClipFilter) -> CollectionSummary:
    """Replace a saved collection's filter definition and return its updated summary."""
    saved = _update_collection(root, name, filters)
    return _summary(root, saved.name, saved.filters)


def delete_collection(root: Path, name: str) -> None:
    """Delete a saved collection. Never touches the clips it matched."""
    _delete_collection(root, name)


def list_collection_clips(
    root: Path,
    name: str,
    *,
    sort: str = "date",
    cursor: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> ClipPage:
    """Return a cursor-paginated page of the clips a collection currently matches."""
    collection = get_collection(root, name)
    return list_clips(root, collection.filters, sort=sort, cursor=cursor, limit=limit)
