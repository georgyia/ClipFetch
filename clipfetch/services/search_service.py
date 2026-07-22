"""Library search service: reliable local text search with a semantic-capability signal.

Text search always works and needs no optional extra: it matches whitespace-separated query terms
against each clip's caption, creator, hashtags, and transcript. The service also reports whether the
semantic extra is installed so the API can advertise a semantic mode and degrade gracefully when it
is not available. Live semantic ranking is served by a later, worker-backed embedder (the API
process does not download or run the embedding model in a request handler — ADR 0001 / plan section
16.2). Until then every mode is served by text search, and ``mode_used`` makes the fallback clear.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from clipfetch.catalog import Catalog, CatalogRecord
from clipfetch.contracts import ClipSummary, clip_summary
from clipfetch.services.catalog_service import InvalidCursorError

DEFAULT_LIMIT = 24
MAX_LIMIT = 100
SEARCH_MODES = ("all", "text", "meaning")


@dataclass(frozen=True)
class SearchResult:
    items: tuple[ClipSummary, ...]
    next_cursor: str | None
    total_matched: int
    mode_used: str
    semantic_available: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [item.to_dict() for item in self.items],
            "next_cursor": self.next_cursor,
            "total_matched": self.total_matched,
            "mode_used": self.mode_used,
            "semantic_available": self.semantic_available,
        }


def semantic_available() -> bool:
    """Whether the optional semantic extra (FastEmbed) is importable in this environment."""
    try:
        return find_spec("fastembed") is not None
    except (ImportError, ValueError):
        return False


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
    return max(1, min(limit, MAX_LIMIT))


def _searchable_text(record: CatalogRecord) -> str:
    parts = [record.caption or "", record.author or "", " ".join(record.hashtags)]
    if record.transcript_text:
        parts.append(record.transcript_text)
    return " ".join(parts).casefold()


def _score(text: str, terms: list[str]) -> int:
    return sum(text.count(term) for term in terms)


def _search_text(
    root: Path, terms: list[str], offset: int, limit: int
) -> tuple[tuple[ClipSummary, ...], int, int]:
    with Catalog.open(root) as catalog:
        present = [
            record
            for record in catalog.all()
            if (root / record.relative_path).is_file()
        ]
        scored = [
            (record, _score(_searchable_text(record), terms))
            for record in present
        ]
        matched = [(record, score) for record, score in scored if score > 0]
        # Stable multi-pass sort: score desc (primary), then newest first, then clip id.
        matched.sort(key=lambda pair: pair[0].clip_id)
        matched.sort(key=lambda pair: pair[0].downloaded_at, reverse=True)
        matched.sort(key=lambda pair: pair[1], reverse=True)
        total = len(matched)
        page = matched[offset : offset + limit]
        topics = {
            (record.platform, record.clip_id): catalog.topic_names(record.platform, record.clip_id)
            for record, _ in page
        }
    items = tuple(
        clip_summary(record, topics=topics.get((record.platform, record.clip_id), ()))
        for record, _ in page
    )
    return items, total, offset + len(items)


def search(
    root: Path,
    query: str,
    *,
    mode: str = "all",
    cursor: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> SearchResult:
    """Run a search. ``mode`` is validated by the caller; unknown modes raise ``ValueError``."""
    if mode not in SEARCH_MODES:
        raise ValueError(f"unknown search mode: {mode}")
    terms = query.casefold().split()
    page_size = _clamp_limit(limit)
    offset = _decode_cursor(cursor) if cursor is not None else 0

    if not terms:
        return SearchResult((), None, 0, "text", semantic_available())

    items, total, next_offset = _search_text(root, terms, offset, page_size)
    next_cursor = _encode_cursor(next_offset) if next_offset < total else None
    # Every mode is currently served by text search; see the module docstring.
    return SearchResult(items, next_cursor, total, "text", semantic_available())
