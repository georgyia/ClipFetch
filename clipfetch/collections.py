"""Dynamic saved collections backed by the shared :class:`ClipFilter`."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from clipfetch.library import ClipFilter, QueryResult, query_library, record_to_dict
from clipfetch.topics import TopicError, load_topics

COLLECTIONS_FILE = ".clipfetch/collections.json"
COLLECTIONS_SCHEMA_VERSION = 1
_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_FILTER_FIELDS = {
    "min_likes",
    "max_likes",
    "min_views",
    "max_views",
    "authors",
    "hashtags",
    "platforms",
    "topics",
    "downloaded_after",
    "downloaded_before",
}


class CollectionError(RuntimeError):
    """Saved collection data is invalid or cannot be resolved."""


@dataclass(frozen=True)
class SavedCollection:
    name: str
    filters: ClipFilter


def collections_path(root: Path) -> Path:
    return root.resolve() / COLLECTIONS_FILE


def load_collections(root: Path) -> tuple[SavedCollection, ...]:
    path = collections_path(root)
    if not path.exists():
        return ()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as err:
        raise CollectionError(f"invalid collections file {path}: {err}") from err
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise CollectionError("unsupported or missing collections schema version")
    raw = value.get("collections")
    if not isinstance(raw, list):
        raise CollectionError("collections must be a list")
    collections = tuple(_saved(item) for item in raw)
    names = [item.name for item in collections]
    if len(names) != len(set(names)):
        raise CollectionError("duplicate collection names are not allowed")
    for item in collections:
        _validate_topics(root, item.filters)
    return collections


def save_collection(root: Path, name: str, filters: ClipFilter) -> SavedCollection:
    normalized = normalize_collection_name(name)
    existing = list(load_collections(root))
    if any(item.name == normalized for item in existing):
        raise CollectionError(f"collection already exists: {normalized}")
    _validate_topics(root, filters)
    saved = SavedCollection(normalized, filters)
    _write(root, (*existing, saved))
    return saved


def update_collection(root: Path, name: str, filters: ClipFilter) -> SavedCollection:
    """Replace an existing collection's filter definition atomically. Raises if it is missing."""
    normalized = normalize_collection_name(name)
    existing = list(load_collections(root))
    if not any(item.name == normalized for item in existing):
        raise CollectionError(f"unknown collection: {normalized}")
    _validate_topics(root, filters)
    replaced = SavedCollection(normalized, filters)
    _write(root, tuple(replaced if item.name == normalized else item for item in existing))
    return replaced


def delete_collection(root: Path, name: str) -> None:
    normalized = normalize_collection_name(name)
    existing = load_collections(root)
    remaining = tuple(item for item in existing if item.name != normalized)
    if len(remaining) == len(existing):
        raise CollectionError(f"unknown collection: {normalized}")
    _write(root, remaining)


def get_collection(root: Path, name: str) -> SavedCollection:
    normalized = normalize_collection_name(name)
    for item in load_collections(root):
        if item.name == normalized:
            return item
    raise CollectionError(f"unknown collection: {normalized}")


def resolve_collection(root: Path, name: str) -> QueryResult:
    return query_library(root, get_collection(root, name).filters)


def normalize_collection_name(value: str) -> str:
    name = value.strip().casefold()
    if not _NAME.fullmatch(name):
        raise CollectionError(
            "collection names must use lowercase letters, numbers, and single hyphens"
        )
    return name


def filter_to_dict(filters: ClipFilter) -> dict[str, Any]:
    return {
        "min_likes": filters.min_likes,
        "max_likes": filters.max_likes,
        "min_views": filters.min_views,
        "max_views": filters.max_views,
        "authors": list(filters.authors),
        "hashtags": list(filters.hashtags),
        "platforms": list(filters.platforms),
        "topics": list(filters.topics),
        "downloaded_after": (
            filters.downloaded_after.isoformat() if filters.downloaded_after else None
        ),
        "downloaded_before": (
            filters.downloaded_before.isoformat() if filters.downloaded_before else None
        ),
    }


def collection_to_dict(collection: SavedCollection) -> dict[str, Any]:
    return {"name": collection.name, "filters": filter_to_dict(collection.filters)}


def export_json(root: Path, result: QueryResult) -> str:
    value = {
        "schema_version": 1,
        "library": ".",
        "matched": result.matched,
        "clips": [record_to_dict(record) for record in result.clips],
    }
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def export_m3u(result: QueryResult) -> str:
    lines = ["#EXTM3U"]
    for record in result.clips:
        path = record.relative_path.replace("\r", "%0D").replace("\n", "%0A")
        if path.startswith("#"):
            path = "./" + path
        lines.append(path)
    return "\n".join(lines) + "\n"


def _saved(value: Any) -> SavedCollection:
    if not isinstance(value, dict) or set(value) != {"name", "filters"}:
        raise CollectionError("each collection must contain only name and filters")
    name = normalize_collection_name(str(value["name"]))
    raw = value["filters"]
    if not isinstance(raw, dict) or set(raw) != _FILTER_FIELDS:
        unknown = set(raw) - _FILTER_FIELDS if isinstance(raw, dict) else set()
        raise CollectionError(f"unsupported or missing collection filter fields: {unknown}")
    try:
        filters = ClipFilter(
            min_likes=_optional_int(raw["min_likes"]),
            max_likes=_optional_int(raw["max_likes"]),
            min_views=_optional_int(raw["min_views"]),
            max_views=_optional_int(raw["max_views"]),
            authors=_strings(raw["authors"]),
            hashtags=_strings(raw["hashtags"]),
            platforms=_strings(raw["platforms"]),
            topics=_strings(raw["topics"]),
            downloaded_after=_optional_date(raw["downloaded_after"]),
            downloaded_before=_optional_date(raw["downloaded_before"]),
        )
    except (TypeError, ValueError) as err:
        raise CollectionError(f"invalid collection filters: {err}") from err
    return SavedCollection(name, filters)


def _write(root: Path, collections: tuple[SavedCollection, ...]) -> None:
    path = collections_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {
        "schema_version": COLLECTIONS_SCHEMA_VERSION,
        "collections": [collection_to_dict(item) for item in collections],
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _validate_topics(root: Path, filters: ClipFilter) -> None:
    if not filters.topics:
        return
    try:
        available = {topic.name for topic in load_topics(root).topics}
    except TopicError as err:
        raise CollectionError(str(err)) from err
    unknown = set(filters.topics) - available
    if unknown:
        raise CollectionError(f"unknown topic(s): {', '.join(sorted(unknown))}")


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError("expected a list of strings")
    return tuple(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TypeError("expected a non-negative integer or null")
    return value


def _optional_date(value: Any) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("expected an ISO date or null")
    return date.fromisoformat(value)
