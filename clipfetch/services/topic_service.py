"""Topic service: read topic definitions and browse a topic like a small channel.

Wraps :mod:`clipfetch.topics` (the same definitions and rules the CLI uses) and reuses
:func:`clipfetch.services.catalog_service.list_clips` for paginated topic browsing, so the topic
taxonomy is never re-implemented in the web layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clipfetch.contracts import ClipPage
from clipfetch.library import ClipFilter, query_library
from clipfetch.services.catalog_service import DEFAULT_LIMIT, list_clips
from clipfetch.topics import TopicError, load_topics


@dataclass(frozen=True)
class TopicSummary:
    """A topic and how many available clips currently carry it."""

    slug: str
    description: str
    clip_count: int

    def to_dict(self) -> dict[str, Any]:
        return {"slug": self.slug, "description": self.description, "clip_count": self.clip_count}


def list_topics(root: Path) -> tuple[TopicSummary, ...]:
    """Return every configured topic with its current available-clip count."""
    config = load_topics(root)
    return tuple(
        TopicSummary(
            slug=topic.name,
            description=topic.description,
            clip_count=query_library(root, ClipFilter(topics=(topic.name,))).matched,
        )
        for topic in config.topics
    )


def get_topic(root: Path, slug: str) -> TopicSummary:
    """Return one topic summary, or raise ``TopicError`` if it is not defined."""
    for topic in list_topics(root):
        if topic.slug == slug:
            return topic
    raise TopicError(f"unknown topic: {slug}")


def list_topic_clips(
    root: Path,
    slug: str,
    *,
    sort: str = "date",
    cursor: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> ClipPage:
    """Return a cursor-paginated page of clips assigned to ``slug``."""
    defined = {topic.name for topic in load_topics(root).topics}
    if slug not in defined:
        raise TopicError(f"unknown topic: {slug}")
    return list_clips(
        root, ClipFilter(topics=(slug,)), sort=sort, cursor=cursor, limit=limit
    )
