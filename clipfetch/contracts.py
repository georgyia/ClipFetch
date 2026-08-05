"""Public transport contracts for the ClipFetch Watch API.

These dataclasses are the stable, serializable shapes the web layer exposes over ``/api/v1``. They
are deliberately separate from the internal :class:`~clipfetch.catalog.CatalogRecord`: a
presentation DTO lets us evolve storage without breaking clients, and — critically — lets us decide
exactly which fields leave the process. Device-specific and transport-sensitive values (the on-disk
``relative_path``, ``file_mtime_ns``, expiring CDN URLs, cookies, raw payloads, and full
transcript/comment bodies) are **never** serialized here; the full transcript and comments are
served by their own endpoints.

Keys are ``snake_case`` and timestamps stay as the catalog's ISO-8601 strings. ``clip_id`` is
exposed as ``id`` to match the existing :func:`clipfetch.library.record_to_dict` contract.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from clipfetch.catalog import CatalogRecord

#: Bumped only for a breaking change to a serialized contract in this module.
CONTRACT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ClipSummary:
    """Lightweight clip shape for rails, grids, and search results."""

    id: str
    platform: str
    author: str | None
    caption: str | None
    likes: int | None
    views: int | None
    comments_count: int | None
    duration_seconds: float | None
    published_at: str | None
    downloaded_at: str
    available: bool
    metadata_state: str
    hashtags: tuple[str, ...]
    topics: tuple[str, ...]
    source_url: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "platform": self.platform,
            "author": self.author,
            "caption": self.caption,
            "likes": self.likes,
            "views": self.views,
            "comments_count": self.comments_count,
            "duration_seconds": self.duration_seconds,
            "published_at": self.published_at,
            "downloaded_at": self.downloaded_at,
            "available": self.available,
            "metadata_state": self.metadata_state,
            "hashtags": list(self.hashtags),
            "topics": list(self.topics),
            "source_url": self.source_url,
        }


@dataclass(frozen=True)
class ClipDetail:
    """Full clip shape for the detail page. Extends the summary with enrichment status."""

    summary: ClipSummary
    shares: int | None
    file_size_bytes: int
    has_transcript: bool
    transcript_status: str | None
    transcript_language: str | None
    has_comments: bool
    comment_status: str | None
    #: Probed technical media details and derived quality tier, or ``None`` if not probed yet.
    media: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        value = dict(self.summary.to_dict())
        value.update(
            {
                "schema_version": CONTRACT_SCHEMA_VERSION,
                "shares": self.shares,
                "file_size_bytes": self.file_size_bytes,
                "has_transcript": self.has_transcript,
                "transcript_status": self.transcript_status,
                "transcript_language": self.transcript_language,
                "has_comments": self.has_comments,
                "comment_status": self.comment_status,
                "media": self.media,
            }
        )
        return value


@dataclass(frozen=True)
class ClipPage:
    """A cursor-paginated slice of clip summaries."""

    items: tuple[ClipSummary, ...]
    next_cursor: str | None
    total_matched: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "items": [item.to_dict() for item in self.items],
            "next_cursor": self.next_cursor,
            "total_matched": self.total_matched,
        }


@dataclass(frozen=True)
class TranscriptView:
    """One clip's stored speech transcript, with the provenance that makes it checkable.

    ``status`` is the enricher's own category — ``complete``, ``silent`` (ran, no speech found),
    ``unsupported``, ``failed`` — or ``None`` when transcription was never attempted. The stored
    ``transcript_error`` is deliberately **not** carried here: it holds ``str(exception)`` from the
    transcription backend, which can name local media paths. The status is the safe, stable signal.
    """

    clip_id: str
    status: str | None
    text: str | None
    language: str | None
    model_id: str | None
    model_revision: str | None
    updated_at: str | None
    #: True when ``text`` was cut to the response cap; the full text stays in the catalog.
    truncated: bool
    character_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_id": self.clip_id,
            "status": self.status,
            "text": self.text,
            "language": self.language,
            "model_id": self.model_id,
            "model_revision": self.model_revision,
            "updated_at": self.updated_at,
            "truncated": self.truncated,
            "character_count": self.character_count,
        }


@dataclass(frozen=True)
class CommentView:
    """One captured comment. Third-party text: render it as text, never as markup."""

    id: str
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "text": self.text}


@dataclass(frozen=True)
class CommentPage:
    """A bounded slice of a clip's captured comments.

    Like :class:`TranscriptView`, this carries the enricher's ``status`` and not its stored error
    string. ``retrieved_at`` is what makes the snapshot honest: these are the comments as they were
    when captured, not as they are now.
    """

    items: tuple[CommentView, ...]
    total: int
    status: str | None
    retrieved_at: str | None
    next_offset: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [item.to_dict() for item in self.items],
            "total": self.total,
            "status": self.status,
            "retrieved_at": self.retrieved_at,
            "next_offset": self.next_offset,
        }


@dataclass(frozen=True)
class ApiError:
    """A safe, machine-readable error. ``message`` is user-facing; no internals leak."""

    code: str
    message: str
    request_id: str | None = None
    recovery_actions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "request_id": self.request_id,
                "details": {"recovery_actions": list(self.recovery_actions)},
            }
        }


def clip_summary(record: CatalogRecord, *, topics: Sequence[str] = ()) -> ClipSummary:
    """Build a :class:`ClipSummary` from a catalog row, excluding device/transport fields."""
    return ClipSummary(
        id=record.clip_id,
        platform=record.platform,
        author=record.author,
        caption=record.caption,
        likes=record.likes,
        views=record.views,
        comments_count=record.comments_count,
        duration_seconds=record.duration_seconds,
        published_at=record.published_at,
        downloaded_at=record.downloaded_at,
        available=record.available,
        metadata_state=record.metadata_state,
        hashtags=tuple(record.hashtags),
        topics=tuple(topics),
        source_url=record.source_url,
    )


def clip_detail(
    record: CatalogRecord,
    *,
    topics: Sequence[str] = (),
    media: dict[str, Any] | None = None,
) -> ClipDetail:
    """Build a :class:`ClipDetail`, reporting enrichment presence without inlining bodies."""
    return ClipDetail(
        summary=clip_summary(record, topics=topics),
        shares=record.shares,
        file_size_bytes=record.file_size,
        has_transcript=record.transcript_text is not None,
        transcript_status=record.transcript_status,
        transcript_language=record.transcript_language,
        has_comments=record.comment_text is not None,
        comment_status=record.comment_status,
        media=media,
    )
