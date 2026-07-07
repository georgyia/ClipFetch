"""Reel discovery: scroll the Instagram Reels feed and harvest video URLs.

Instagram loads the feed through JSON API responses whose media items carry a
``code`` (shortcode) and ``video_versions`` (direct CDN video URLs). Endpoint
paths change frequently, so instead of hardcoding them we listen to *every*
JSON response from instagram.com and walk the payload for anything shaped
like a video item. New reels are reported through a callback the moment they
are found, so downloads can start while scrolling continues.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Optional

from playwright.sync_api import BrowserContext, Page, Response

from clipfetch.errors import ExtractionError, NotLoggedInError

REELS_URL = "https://www.instagram.com/reels/"
_SCROLL_PAUSE_S = 0.6
_MAX_JSON_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class Reel:
    """A downloadable reel: its shortcode and best-quality video URL."""

    shortcode: str
    video_url: str


def _best_video_url(versions: Any) -> Optional[str]:
    """Pick the highest-resolution URL from a ``video_versions`` list."""
    if not isinstance(versions, list):
        return None
    candidates = [v for v in versions if isinstance(v, dict) and v.get("url")]
    if not candidates:
        return None
    best = max(candidates, key=lambda v: v.get("width") or 0)
    return best["url"]


def find_reels(node: Any) -> Iterator[Reel]:
    """Recursively yield every video item found anywhere in an API payload."""
    if isinstance(node, dict):
        code = node.get("code")
        url = _best_video_url(node.get("video_versions"))
        if isinstance(code, str) and code and url:
            yield Reel(shortcode=code, video_url=url)
            return  # a matched media item holds no further items
        for value in node.values():
            yield from find_reels(value)
    elif isinstance(node, list):
        for item in node:
            yield from find_reels(item)


class ReelCollector:
    """Accumulates unique reels from feed responses up to a limit.

    ``active`` gates collection: responses that arrive while the page is not
    on the Reels feed (e.g. leftover home-feed requests right after login)
    also contain videos and must not be picked up.
    """

    def __init__(
        self,
        limit: int,
        on_reel: Callable[[Reel], None],
        active: Optional[Callable[[], bool]] = None,
    ) -> None:
        self._limit = limit
        self._on_reel = on_reel
        self._active = active or (lambda: True)
        self._seen: set[str] = set()
        self.reels: list[Reel] = []

    @property
    def full(self) -> bool:
        return len(self.reels) >= self._limit

    def handle_response(self, response: Response) -> None:
        if self.full or not self._active() or not self._looks_like_api_json(response):
            return
        try:
            payload = response.json()
        except Exception:  # non-JSON body, truncated stream, navigation race
            return
        for reel in find_reels(payload):
            if self.full:
                return
            if reel.shortcode in self._seen:
                continue
            self._seen.add(reel.shortcode)
            self.reels.append(reel)
            self._on_reel(reel)

    @staticmethod
    def _looks_like_api_json(response: Response) -> bool:
        if "instagram.com" not in response.url or response.status != 200:
            return False
        headers = response.headers
        if "application/json" not in headers.get("content-type", ""):
            return False
        try:
            length = int(headers.get("content-length", 0))
        except ValueError:
            return False
        return length <= _MAX_JSON_BYTES


def _open_feed(context: BrowserContext, count: int, on_reel: Callable[[Reel], None]) -> tuple[Page, ReelCollector]:
    # A fresh page keeps traffic from previously opened pages (the home feed
    # right after login, most notably) away from the collector; the leftovers
    # are closed so they stop loading their own feeds in the background.
    page = context.new_page()
    for other in list(context.pages):
        if other is not page:
            other.close()

    collector = ReelCollector(count, on_reel, active=lambda: page.url.startswith(REELS_URL))
    page.on("response", collector.handle_response)
    page.goto(REELS_URL, wait_until="domcontentloaded")
    if "/accounts/login" in page.url:
        raise NotLoggedInError(
            "Instagram sent us to the login page — your saved session has "
            "expired. Run again with --headed and sign in."
        )
    return page, collector


def collect_reels(
    context: BrowserContext,
    count: int,
    on_reel: Callable[[Reel], None],
    on_progress: Optional[Callable[[int], None]] = None,
    stall_timeout_s: float = 45,
) -> list[Reel]:
    """Scroll the Reels feed until ``count`` unique reels are collected.

    Each reel is passed to ``on_reel`` as soon as it is discovered. Raises
    :class:`ExtractionError` if the feed stops yielding new reels for
    ``stall_timeout_s`` seconds before the target is reached.
    """
    page, collector = _open_feed(context, count, on_reel)
    viewport = page.viewport_size or {"width": 1280, "height": 900}
    page.mouse.move(viewport["width"] / 2, viewport["height"] / 2)

    last_progress = 0
    last_new_reel_at = time.monotonic()
    while not collector.full:
        # Wheel gestures advance the snap-scrolled feed without needing
        # keyboard focus (ArrowDown is ignored until a reel is focused).
        page.mouse.wheel(0, viewport["height"])
        page.wait_for_timeout(_SCROLL_PAUSE_S * 1000)

        found = len(collector.reels)
        if found > last_progress:
            last_progress = found
            last_new_reel_at = time.monotonic()
            if on_progress:
                on_progress(found)
        elif time.monotonic() - last_new_reel_at > stall_timeout_s:
            if found:
                break  # partial result beats an error deep into a session
            raise ExtractionError(
                "The Reels feed loaded but yielded no downloadable videos — "
                "Instagram may have changed its API or is showing a checkpoint "
                "page. Try again with --headed to see what the browser sees."
            )
    return collector.reels
