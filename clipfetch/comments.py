"""Explicit, bounded Instagram comment enrichment with minimal local storage."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlencode

from clipfetch.catalog import Catalog, CatalogRecord
from clipfetch.errors import ClipFetchError
from clipfetch.library import ClipFilter, query_library

DEFAULT_MAX_COMMENTS = 20
HARD_MAX_COMMENTS = 100
MAX_PAGES_PER_CLIP = 10
MAX_COMMENT_CHARACTERS = 4_000
MAX_SINGLE_COMMENT_CHARACTERS = 1_000
MIN_REQUEST_INTERVAL_SECONDS = 1.0
_APP_ID = "936619743392459"
_HOME = "https://www.instagram.com"


class CommentsError(ClipFetchError):
    """Comment enrichment could not be configured or completed safely."""


class CommentOutcomeError(Exception):
    status = "failed"


class CommentsDisabled(CommentOutcomeError):
    status = "disabled"


class ClipDeleted(CommentOutcomeError):
    status = "deleted"


class ClipUnavailable(CommentOutcomeError):
    status = "unavailable"


class AuthenticationCheckpoint(CommentOutcomeError):
    status = "authentication-checkpoint"


class RateLimited(CommentOutcomeError):
    status = "rate-limited"


class BackendFailure(CommentOutcomeError):
    status = "failed"


@dataclass(frozen=True)
class CommentItem:
    comment_id: str
    text: str


@dataclass(frozen=True)
class CommentPage:
    comments: tuple[CommentItem, ...]
    next_cursor: str | None = None


class CommentBackend(Protocol):
    def resolve_media_id(self, record: CatalogRecord) -> str: ...

    def fetch_page(
        self,
        media_id: str,
        cursor: str | None,
        limit: int,
    ) -> CommentPage: ...


@dataclass(frozen=True)
class CommentEnrichmentReport:
    selected: int
    completed: int
    skipped: int
    empty: int
    disabled: int
    deleted: int
    unavailable: int
    authentication_checkpoint: int
    rate_limited: int
    failed: int


class RequestLimiter:
    """Enforce a global request start interval with an injectable clock."""

    def __init__(
        self,
        interval: float = MIN_REQUEST_INTERVAL_SECONDS,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.interval = interval
        self.clock = clock
        self.sleep = sleep
        self._last_request: float | None = None

    def wait(self) -> None:
        now = self.clock()
        if self._last_request is not None:
            delay = self.interval - (now - self._last_request)
            if delay > 0:
                self.sleep(delay)
                now = self.clock()
        self._last_request = now


class InstagramCommentBackend:
    """Small Playwright request adapter for Instagram's authenticated web API."""

    def __init__(self, context: Any) -> None:
        self._request = context.request

    def resolve_media_id(self, record: CatalogRecord) -> str:
        payload = self._get_json(
            f"{_HOME}/api/v1/media/shortcode/{record.clip_id}/info/",
            referer=f"{_HOME}/reel/{record.clip_id}/",
        )
        items = payload.get("items")
        if not isinstance(items, list) or not items or not isinstance(items[0], dict):
            raise ClipDeleted("media is no longer returned by Instagram")
        item = items[0]
        if item.get("comments_disabled") is True:
            raise CommentsDisabled("comments are disabled")
        media_id = item.get("pk") or item.get("id")
        if not isinstance(media_id, (str, int)) or not str(media_id):
            raise BackendFailure("Instagram response omitted the media id")
        return str(media_id)

    def fetch_page(
        self,
        media_id: str,
        cursor: str | None,
        limit: int,
    ) -> CommentPage:
        query: dict[str, str | int] = {
            "can_support_threading": "true",
            "permalink_enabled": "false",
            "count": limit,
        }
        if cursor:
            query["min_id"] = cursor
        payload = self._get_json(
            f"{_HOME}/api/v1/media/{media_id}/comments/?{urlencode(query)}",
            referer=f"{_HOME}/",
        )
        if payload.get("comments_disabled") is True:
            raise CommentsDisabled("comments are disabled")
        raw_comments = payload.get("comments")
        comments = []
        if isinstance(raw_comments, list):
            for value in raw_comments:
                if not isinstance(value, dict):
                    continue
                if value.get("is_deleted") is True or value.get("status") == "deleted":
                    continue
                comment_id = value.get("pk") or value.get("id")
                text = value.get("text")
                if isinstance(comment_id, (str, int)) and isinstance(text, str):
                    comments.append(CommentItem(str(comment_id), text))
        cursor_value = (
            payload.get("next_min_id")
            or payload.get("next_max_id")
            or payload.get("next_cursor")
        )
        has_more = payload.get("has_more_comments") is True or cursor_value is not None
        next_cursor = str(cursor_value) if has_more and cursor_value is not None else None
        return CommentPage(tuple(comments), next_cursor)

    def _get_json(self, url: str, *, referer: str) -> dict[str, Any]:
        response = self._request.get(
            url,
            headers={
                "Referer": referer,
                "X-IG-App-ID": _APP_ID,
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=30_000,
        )
        try:
            status = int(response.status)
            if status == 429:
                raise RateLimited("Instagram returned HTTP 429")
            if status in (401, 403):
                raise AuthenticationCheckpoint(f"Instagram returned HTTP {status}")
            if status == 404:
                raise ClipUnavailable("Instagram returned HTTP 404")
            if status >= 400:
                raise BackendFailure(f"Instagram returned HTTP {status}")
            try:
                payload = response.json()
            except Exception as err:
                raise BackendFailure("Instagram returned malformed JSON") from err
            if not isinstance(payload, dict):
                raise BackendFailure("Instagram returned an unexpected response")
            message = str(payload.get("message") or "").casefold()
            if payload.get("checkpoint_url") or "checkpoint" in message or "login" in message:
                raise AuthenticationCheckpoint(message or "authentication checkpoint")
            if payload.get("status") == "fail":
                if "not found" in message or "deleted" in message:
                    raise ClipDeleted(message)
                raise BackendFailure(message or "Instagram request failed")
            return payload
        finally:
            try:
                response.dispose()
            except Exception:
                pass


def select_comment_records(
    root: Path,
    filters: ClipFilter | None = None,
) -> tuple[CatalogRecord, ...]:
    """Apply local filters before the caller opens an authenticated browser."""
    result = query_library(root, filters)
    return tuple(
        record
        for record in result.clips
        if record.platform == "instagram"
        and record.available
        and (root / record.relative_path).is_file()
    )


def enrich_comments(
    root: Path,
    backend: CommentBackend,
    records: Sequence[CatalogRecord],
    *,
    max_comments: int = DEFAULT_MAX_COMMENTS,
    force: bool = False,
    limiter: RequestLimiter | None = None,
    on_progress: Callable[[int, int, str, CatalogRecord], None] | None = None,
) -> CommentEnrichmentReport:
    """Fetch bounded comment pages and commit every clip outcome independently."""
    if max_comments < 1 or max_comments > HARD_MAX_COMMENTS:
        raise CommentsError(
            f"max comments must be between 1 and {HARD_MAX_COMMENTS}"
        )
    limiter = limiter or RequestLimiter()
    counters = {
        "completed": 0,
        "skipped": 0,
        "empty": 0,
        "disabled": 0,
        "deleted": 0,
        "unavailable": 0,
        "authentication-checkpoint": 0,
        "rate-limited": 0,
        "failed": 0,
    }
    terminal = {"complete", "empty", "disabled", "deleted", "unavailable"}
    total = len(records)
    for index, stale_record in enumerate(records, start=1):
        with Catalog.open(root) as catalog:
            record = catalog.get(stale_record.platform, stale_record.clip_id)
        if record is None:
            counters["failed"] += 1
            continue
        if not force and record.comment_status in terminal:
            status = "skipped"
            counters[status] += 1
        else:
            try:
                limiter.wait()
                media_id = backend.resolve_media_id(record)
                retained: list[tuple[str, str]] = []
                seen_ids: set[str] = set()
                seen_text: set[str] = set()
                cursor: str | None = None
                seen_cursors: set[str] = set()
                for _ in range(MAX_PAGES_PER_CLIP):
                    limiter.wait()
                    page = backend.fetch_page(
                        media_id,
                        cursor,
                        min(50, max_comments - len(retained)),
                    )
                    _retain_comments(
                        retained,
                        page.comments,
                        seen_ids,
                        seen_text,
                        max_comments,
                    )
                    if len(retained) >= max_comments or not page.next_cursor:
                        break
                    if page.next_cursor in seen_cursors:
                        break
                    seen_cursors.add(page.next_cursor)
                    cursor = page.next_cursor
                status = "complete" if retained else "empty"
                with Catalog.open(root) as catalog:
                    catalog.set_comments(record.platform, record.clip_id, retained, status=status)
                counters["completed" if retained else "empty"] += 1
            except KeyboardInterrupt:
                raise
            except (CommentsDisabled, ClipDeleted, ClipUnavailable) as err:
                status = err.status
                with Catalog.open(root) as catalog:
                    catalog.set_comments(
                        record.platform,
                        record.clip_id,
                        [],
                        status=status,
                        error=str(err),
                    )
                counters[status] += 1
            except (AuthenticationCheckpoint, RateLimited, BackendFailure) as err:
                status = err.status
                with Catalog.open(root) as catalog:
                    catalog.set_comment_status(
                        record.platform,
                        record.clip_id,
                        status,
                        str(err),
                    )
                counters[status] += 1
            except Exception as err:
                status = "failed"
                with Catalog.open(root) as catalog:
                    catalog.set_comment_status(
                        record.platform,
                        record.clip_id,
                        status,
                        str(err),
                    )
                counters[status] += 1
        if on_progress:
            on_progress(index, total, status, record)
    return CommentEnrichmentReport(
        total,
        counters["completed"],
        counters["skipped"],
        counters["empty"],
        counters["disabled"],
        counters["deleted"],
        counters["unavailable"],
        counters["authentication-checkpoint"],
        counters["rate-limited"],
        counters["failed"],
    )


def purge_comments(root: Path) -> int:
    if not root.is_dir():
        raise CommentsError(f"library directory does not exist: {root.resolve()}")
    with Catalog.open(root) as catalog:
        return catalog.purge_comments()


def normalize_comment(value: str) -> str:
    return " ".join(value.split())


def _retain_comments(
    retained: list[tuple[str, str]],
    candidates: Sequence[CommentItem],
    seen_ids: set[str],
    seen_text: set[str],
    max_comments: int,
) -> None:
    used = sum(len(text) for _, text in retained) + max(0, len(retained) - 1)
    for item in candidates:
        text = normalize_comment(item.text)[:MAX_SINGLE_COMMENT_CHARACTERS].rstrip()
        if (
            not item.comment_id
            or not text
            or item.comment_id in seen_ids
            or text in seen_text
            or len(retained) >= max_comments
        ):
            continue
        separator = 1 if retained else 0
        remaining = MAX_COMMENT_CHARACTERS - used - separator
        if remaining <= 0:
            break
        text = text[:remaining].rstrip()
        if not text:
            break
        retained.append((item.comment_id, text))
        seen_ids.add(item.comment_id)
        seen_text.add(text)
        used += separator + len(text)
