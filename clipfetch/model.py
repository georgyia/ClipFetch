"""Platform-agnostic data types shared across ClipFetch."""

from __future__ import annotations

import enum
from dataclasses import dataclass


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
class Clip:
    """A downloadable short video, independent of the source platform.

    ``ident`` is the platform's stable id (Instagram shortcode, TikTok/YouTube
    video id) and is used both for de-duplication and for the output filename.
    ``referer`` is set when the video CDN rejects requests without one.

    ``url``, ``author``, ``caption`` and ``likes`` are best-effort metadata
    pulled from the same feed payload the video URL came from; any of them may
    be ``None`` when the platform did not include it. They feed the optional
    ``--metadata`` JSON sidecar and are never required for downloading.
    """

    platform: str
    ident: str
    video_url: str
    referer: str | None = None
    url: str | None = None  # canonical permalink of the post
    author: str | None = None
    caption: str | None = None
    likes: int | None = None

    def metadata(self) -> dict:
        """The clip's sidecar-worthy fields, for ``--metadata`` JSON files."""
        return {
            "platform": self.platform,
            "id": self.ident,
            "url": self.url,
            "author": self.author,
            "caption": self.caption,
            "likes": self.likes,
        }
