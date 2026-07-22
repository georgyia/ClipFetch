"""Home rail composition.

Assembles the home screen as an ordered list of rails from the active library and device state,
using only deterministic rules (no learned ranking): Continue Watching and Favorites from app state,
Recently Added from the catalog, and one rail per non-empty topic and saved collection. Rails with
no content are omitted, and ordering is stable for a given library state so tests and the UI agree.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clipfetch.appstate import AppState
from clipfetch.catalog import CatalogError
from clipfetch.collections import CollectionError
from clipfetch.contracts import ClipPage, ClipSummary
from clipfetch.services import catalog_service, collection_service, topic_service
from clipfetch.topics import TopicError

DEFAULT_RAIL_LIMIT = 12
MAX_TOPIC_RAILS = 6


@dataclass(frozen=True)
class Rail:
    id: str
    title: str
    kind: str
    destination: str
    items: tuple[ClipSummary, ...]
    next_cursor: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "kind": self.kind,
            "destination": self.destination,
            "items": [item.to_dict() for item in self.items],
            "next_cursor": self.next_cursor,
        }


def _titleize(slug: str) -> str:
    return slug.replace("-", " ").title()


def _summaries_from_ids(root: Path, ids: tuple[str, ...]) -> tuple[ClipSummary, ...]:
    summaries: list[ClipSummary] = []
    for clip_id in ids:
        try:
            summaries.append(catalog_service.get_clip(root, clip_id).summary)
        except CatalogError:
            continue  # a favorited/watched clip whose media or record is gone is simply skipped
    return tuple(summaries)


def _continue_ids(appstate: AppState, library_id: str, limit: int) -> tuple[str, ...]:
    incomplete = [
        entry.clip_id
        for entry in appstate.recent_playback(library_id, limit=limit * 2)
        if not entry.completed
    ]
    return tuple(incomplete[:limit])


def _topic_rails(root: Path, limit: int) -> list[Rail]:
    try:
        topics = [topic for topic in topic_service.list_topics(root) if topic.clip_count > 0]
    except TopicError:
        return []
    topics.sort(key=lambda topic: (-topic.clip_count, topic.slug))
    rails: list[Rail] = []
    for topic in topics[:MAX_TOPIC_RAILS]:
        page = topic_service.list_topic_clips(root, topic.slug, limit=limit)
        if page.items:
            rails.append(
                Rail(
                    id=f"topic:{topic.slug}",
                    title=_titleize(topic.slug),
                    kind="topic",
                    destination=f"/topics/{topic.slug}",
                    items=page.items,
                    next_cursor=page.next_cursor,
                )
            )
    return rails


def _collection_rails(root: Path, limit: int) -> list[Rail]:
    try:
        collections = [
            item for item in collection_service.list_collections(root) if item.clip_count > 0
        ]
    except CollectionError:
        return []
    rails: list[Rail] = []
    for collection in collections:
        page = collection_service.list_collection_clips(root, collection.id, limit=limit)
        if page.items:
            rails.append(
                Rail(
                    id=f"collection:{collection.id}",
                    title=_titleize(collection.id),
                    kind="collection",
                    destination=f"/collections/{collection.id}",
                    items=page.items,
                    next_cursor=page.next_cursor,
                )
            )
    return rails


def build_home(
    root: Path,
    appstate: AppState,
    library_id: str,
    *,
    rail_limit: int = DEFAULT_RAIL_LIMIT,
) -> tuple[Rail, ...]:
    """Compose the ordered, non-empty rails for the home screen."""
    rails: list[Rail] = []

    continue_items = _summaries_from_ids(root, _continue_ids(appstate, library_id, rail_limit))
    if continue_items:
        rails.append(
            Rail("continue", "Continue Watching", "continue", "/library/recent",
                 continue_items, None)
        )

    recent = catalog_service.list_clips(root, sort="date", limit=rail_limit)
    if recent.items:
        rails.append(
            Rail("recent", "Recently Added", "recent", "/library/recent",
                 recent.items, recent.next_cursor)
        )

    favorite_ids = appstate.list_favorites(library_id)[:rail_limit]
    favorite_items = _summaries_from_ids(root, favorite_ids)
    if favorite_items:
        rails.append(
            Rail("favorites", "Favorites", "favorites", "/library/favorites", favorite_items, None)
        )

    rails.extend(_topic_rails(root, rail_limit))
    rails.extend(_collection_rails(root, rail_limit))
    return tuple(rails)


def rail_page(
    root: Path,
    appstate: AppState,
    library_id: str,
    rail_id: str,
    *,
    cursor: str | None = None,
    limit: int = DEFAULT_RAIL_LIMIT,
) -> ClipPage:
    """Return one page of a single rail, for "see all" / lazy pagination.

    Catalog-backed rails (recent, topic, collection) paginate by cursor; the app-state rails
    (continue, favorites) return a single bounded page. Raises ``KeyError`` for an unknown rail.
    """
    if rail_id == "recent":
        return catalog_service.list_clips(root, sort="date", cursor=cursor, limit=limit)
    if rail_id == "continue":
        items = _summaries_from_ids(root, _continue_ids(appstate, library_id, limit))
        return ClipPage(items=items, next_cursor=None, total_matched=len(items))
    if rail_id == "favorites":
        items = _summaries_from_ids(root, appstate.list_favorites(library_id)[:limit])
        return ClipPage(items=items, next_cursor=None, total_matched=len(items))
    if rail_id.startswith("topic:"):
        return topic_service.list_topic_clips(
            root, rail_id[len("topic:") :], cursor=cursor, limit=limit
        )
    if rail_id.startswith("collection:"):
        return collection_service.list_collection_clips(
            root, rail_id[len("collection:") :], cursor=cursor, limit=limit
        )
    raise KeyError(rail_id)
