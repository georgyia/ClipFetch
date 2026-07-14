"""Platform-agnostic data types shared across ClipFetch."""

from __future__ import annotations

import enum
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

_HASHTAG = re.compile(r"#([\w]+)", re.UNICODE)
_MAX_TIMESTAMP = 4_102_444_800  # 2100-01-01 UTC; also rejects ms/us timestamps.
_MAX_COUNTER = 9_223_372_036_854_775_807  # SQLite signed INTEGER maximum.


class Quality(enum.Enum):
    """Which rendition to prefer when a clip offers several."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    def choose(self, ranked: list):
        """Pick from a list already sorted low → high resolution."""
        if not ranked:
            raise ValueError("no renditions to choose from")
        if self is Quality.HIGH:
            return ranked[-1]
        if self is Quality.LOW:
            return ranked[0]
        return ranked[len(ranked) // 2]  # MEDIUM: the middle rendition


@dataclass(frozen=True)
class ClipMetadata:
    """Typed, platform-neutral, persistable clip metadata.

    Unknown values remain ``None``. This object deliberately has no CDN URL,
    cookies, referer, or other expiring transport/session data.
    """

    platform: str
    clip_id: str
    url: str | None = None
    author: str | None = None
    caption: str | None = None
    likes: int | None = None
    hashtags: tuple[str, ...] = ()
    views: int | None = None
    comments_count: int | None = None
    shares: int | None = None
    duration_seconds: float | None = None
    published_at: datetime | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic schema-v2 JSON-safe metadata."""
        return {
            "schema_version": 2,
            "platform": self.platform,
            "id": self.clip_id,
            "url": self.url,
            "author": self.author,
            "caption": self.caption,
            "likes": self.likes,
            "hashtags": list(self.hashtags),
            "views": self.views,
            "comments_count": self.comments_count,
            "shares": self.shares,
            "duration_seconds": self.duration_seconds,
            "published_at": (
                self.published_at.astimezone(timezone.utc).isoformat()
                if self.published_at
                else None
            ),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ClipMetadata:
        """Read both legacy unversioned and schema-v2 sidecar mappings."""
        raw_platform = value.get("platform")
        raw_clip_id = value.get("id")
        caption = value.get("caption") if isinstance(value.get("caption"), str) else None
        raw_hashtags = value.get("hashtags")
        hashtags = (
            normalize_hashtags(raw_hashtags)
            if isinstance(raw_hashtags, list)
            else extract_hashtags(caption)
        )
        return cls(
            platform=raw_platform if isinstance(raw_platform, str) else "",
            clip_id=raw_clip_id if isinstance(raw_clip_id, str) else "",
            url=value.get("url") if isinstance(value.get("url"), str) else None,
            author=value.get("author") if isinstance(value.get("author"), str) else None,
            caption=caption,
            likes=optional_count(value.get("likes")),
            hashtags=hashtags,
            views=optional_count(value.get("views")),
            comments_count=optional_count(value.get("comments_count")),
            shares=optional_count(value.get("shares")),
            duration_seconds=optional_duration(value.get("duration_seconds")),
            published_at=parse_datetime(value.get("published_at")),
        )


@dataclass(frozen=True)
class Clip:
    """A downloadable short video, independent of the source platform.

    ``ident`` is the platform's stable id (Instagram shortcode, TikTok/YouTube
    video id) and is used both for de-duplication and for the output filename.
    ``referer`` is set when the video CDN rejects requests without one.

    All remaining fields are best-effort metadata pulled from the same feed
    payload as the video URL. Unknown values stay ``None`` and are never
    required for downloading. :meth:`normalized_metadata` separates them from
    the expiring transport/session fields before persistence.
    """

    platform: str
    ident: str
    video_url: str
    referer: str | None = None
    url: str | None = None  # canonical permalink of the post
    author: str | None = None
    caption: str | None = None
    likes: int | None = None
    hashtags: tuple[str, ...] = ()
    views: int | None = None
    comments_count: int | None = None
    shares: int | None = None
    duration_seconds: float | None = None
    published_at: datetime | None = None

    def normalized_metadata(self) -> ClipMetadata:
        """Separate persistable metadata from expiring download transport fields."""
        return ClipMetadata(
            platform=self.platform,
            clip_id=self.ident,
            url=self.url,
            author=self.author,
            caption=self.caption,
            likes=self.likes,
            hashtags=self.hashtags or extract_hashtags(self.caption),
            views=self.views,
            comments_count=self.comments_count,
            shares=self.shares,
            duration_seconds=self.duration_seconds,
            published_at=self.published_at,
        )

    def metadata(self) -> dict[str, Any]:
        """The clip's sidecar-worthy fields, for ``--metadata`` JSON files."""
        return self.normalized_metadata().as_dict()


def extract_hashtags(caption: str | None) -> tuple[str, ...]:
    """Extract Unicode hashtags, casefolded and de-duplicated in source order."""
    if not caption:
        return ()
    ordered: list[str] = []
    seen: set[str] = set()
    for match in _HASHTAG.finditer(caption):
        tag = match.group(1).casefold()
        if tag and tag not in seen:
            ordered.append(tag)
            seen.add(tag)
    return tuple(ordered)


def normalize_hashtags(values: list[Any]) -> tuple[str, ...]:
    """Normalize an already-separated hashtag list from a sidecar."""
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        tag = value.removeprefix("#").casefold()
        if tag and _HASHTAG.fullmatch("#" + tag) and tag not in seen:
            ordered.append(tag)
            seen.add(tag)
    return tuple(ordered)


def optional_count(value: Any) -> int | None:
    """Normalize a non-negative integer counter without treating bool as int."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 0 <= value <= _MAX_COUNTER else None
    if isinstance(value, str) and value.isascii() and value.isdigit():
        parsed = int(value)
        return parsed if parsed <= _MAX_COUNTER else None
    return None


def optional_duration(value: Any) -> float | None:
    """Normalize a finite non-negative duration in seconds."""
    if isinstance(value, bool):
        return None
    try:
        duration = float(value)
    except (TypeError, ValueError):
        return None
    return duration if duration >= 0 and math.isfinite(duration) else None


def timestamp_seconds(value: Any) -> datetime | None:
    """Normalize a plausible Unix-seconds timestamp to aware UTC."""
    seconds = optional_count(value)
    if seconds is None or seconds > _MAX_TIMESTAMP:
        return None
    try:
        return datetime.fromtimestamp(seconds, timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def parse_datetime(value: Any) -> datetime | None:
    """Parse a persisted ISO-8601 timestamp, requiring timezone awareness."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)
