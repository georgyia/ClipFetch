"""Platform-agnostic data types shared across ClipFetch."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Optional


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
    """

    platform: str
    ident: str
    video_url: str
    referer: Optional[str] = None
