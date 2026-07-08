"""The Platform interface every source (Instagram, TikTok, YouTube) implements.

A platform knows three things ClipFetch needs: where its short-video feed
lives, how to tell its API responses apart from noise, and how to pull
downloadable clips out of those responses. Everything else — the browser
session, scrolling, the parallel downloader, the terminal UI — is shared.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any

from clipfetch.model import Clip, Quality


class Platform(ABC):
    """Describes one short-video source."""

    key: str  # stable identifier, e.g. "instagram"
    label: str  # human name, e.g. "Instagram"
    flag: str  # CLI flag without the dash, e.g. "reels"
    noun: str  # singular unit, e.g. "reel"
    host: str  # bare domain used to match API responses, e.g. "instagram.com"

    # Login handling. ``session_cookie`` is the cookie whose presence proves a
    # signed-in session; ``None`` means the platform is used without an
    # enforced login (best-effort).
    login_url: str
    session_cookie: str | None = None
    supports_target: bool = False  # accepts "@username"
    # When True, clips are fetched through the live browser session (their URLs
    # are fingerprint-bound) instead of the parallel urllib downloader.
    needs_browser_download: bool = False
    # Extraction works but downloads are unreliable (platform anti-bot).
    experimental: bool = False

    @abstractmethod
    def feed_url(self, target: str | None = None) -> str:
        """URL of the feed to scroll (optionally for a specific account)."""

    def is_on_feed(self, url: str, target: str | None = None) -> bool:
        """Whether ``url`` is (still) the feed we opened — gates collection."""
        return url.startswith(self.feed_url(target).split("?", 1)[0])

    @abstractmethod
    def find_clips(self, payload: Any, quality: Quality) -> Iterator[Clip]:
        """Yield every downloadable clip found in one API response payload."""

    def collect_target(self, context, target, quality, count, on_clip, already_have):
        """Collect clips for a single account (``@user`` mode).

        Return ``None`` to fall back to the generic feed-scrolling collector;
        override when a platform needs a bespoke per-account strategy.
        """
        return None
