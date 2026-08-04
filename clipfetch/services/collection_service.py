"""Collection service: CRUD, membership, and browsing for saved collections.

Wraps :mod:`clipfetch.collections`, so the web layer and the CLI share the exact same validation and
query semantics. A collection is a saved filter, an explicit member list, or both — see that
module for the model. Browsing reuses :func:`clipfetch.services.catalog_service.list_selection`
for pagination, so a page contains the union in one consistent sort order.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clipfetch.collections import (
    add_clips as _add_clips,
)
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
    remove_clips as _remove_clips,
)
from clipfetch.collections import (
    update_collection as _update_collection,
)
from clipfetch.contracts import ClipPage
from clipfetch.library import ClipFilter, find_clip, query_selection
from clipfetch.services.catalog_service import DEFAULT_LIMIT, list_selection


@dataclass(frozen=True)
class CollectionSummary:
    """A saved collection: its id, its filter definition, its pinned members, and its clip count.

    ``filters`` is ``None`` for a collection with no dynamic rule. ``clip_count`` is the size of
    the union, so it never disagrees with what browsing the collection returns.
    """

    id: str
    filters: dict[str, Any] | None
    clip_count: int
    pinned: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "filters": self.filters,
            "clip_count": self.clip_count,
            "pinned": list(self.pinned),
            "pinned_count": len(self.pinned),
        }


def _summary(
    root: Path, name: str, filters: ClipFilter | None, pinned: tuple[str, ...]
) -> CollectionSummary:
    return CollectionSummary(
        id=name,
        filters=None if filters is None else filter_to_dict(filters),
        clip_count=query_selection(root, filters, pinned).matched,
        pinned=pinned,
    )


def list_collections(root: Path) -> tuple[CollectionSummary, ...]:
    """Return every saved collection with its current clip count."""
    return tuple(
        _summary(root, item.name, item.filters, item.clips) for item in load_collections(root)
    )


def get_collection_summary(root: Path, name: str) -> CollectionSummary:
    """Return one collection summary, or raise ``CollectionError`` if it does not exist."""
    collection = get_collection(root, name)
    return _summary(root, collection.name, collection.filters, collection.clips)


def create_collection(
    root: Path, name: str, filters: ClipFilter | None, clips: Sequence[str] = ()
) -> CollectionSummary:
    """Save a new collection through the shared validators and return its summary."""
    _require_clips_exist(root, clips)
    saved = save_collection(root, name, filters, clips)
    return _summary(root, saved.name, saved.filters, saved.clips)


def update_collection(root: Path, name: str, filters: ClipFilter | None) -> CollectionSummary:
    """Replace a saved collection's filter definition and return its updated summary."""
    saved = _update_collection(root, name, filters)
    return _summary(root, saved.name, saved.filters, saved.clips)


def add_clips(root: Path, name: str, clip_ids: Sequence[str]) -> CollectionSummary:
    """Pin clips into a collection. Raises ``CatalogError`` if any id is not in this library."""
    _require_clips_exist(root, clip_ids)
    saved = _add_clips(root, name, clip_ids)
    return _summary(root, saved.name, saved.filters, saved.clips)


def remove_clips(root: Path, name: str, clip_ids: Sequence[str]) -> CollectionSummary:
    """Unpin clips from a collection.

    Deliberately does not check that the ids still exist: unpinning has to keep working after a
    clip has left the library, which is exactly when a stale pin needs cleaning up.
    """
    saved = _remove_clips(root, name, clip_ids)
    return _summary(root, saved.name, saved.filters, saved.clips)


def delete_collection(root: Path, name: str) -> None:
    """Delete a saved collection. Never touches the clips it matched or contained."""
    _delete_collection(root, name)


def list_collection_clips(
    root: Path,
    name: str,
    *,
    sort: str = "date",
    cursor: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> ClipPage:
    """Return a cursor-paginated page of a collection's clips: filter matches plus pinned ones."""
    collection = get_collection(root, name)
    return list_selection(
        root, collection.filters, collection.clips, sort=sort, cursor=cursor, limit=limit
    )


def _require_clips_exist(root: Path, clip_ids: Sequence[str]) -> None:
    for clip_id in clip_ids:
        find_clip(root, clip_id)
