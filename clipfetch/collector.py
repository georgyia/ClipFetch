"""Scroll a platform's feed and harvest clips from its API responses.

This is platform-agnostic: it drives the browser and watches network traffic,
delegating "is this a feed response?" and "what clips are in it?" to the
:class:`~clipfetch.platforms.base.Platform`. New clips are reported through a
callback the moment they are found, so downloads can start while scrolling
continues.
"""

from __future__ import annotations

import time
from typing import Callable, Optional, Set

from playwright.sync_api import BrowserContext, Page, Response

from clipfetch.errors import ExtractionError, NotLoggedInError
from clipfetch.model import Clip, Quality
from clipfetch.platforms.base import Platform

_SCROLL_PAUSE_S = 0.6
_MAX_JSON_BYTES = 8 * 1024 * 1024
_DEFAULT_STALL_TIMEOUT_S = 45


class ClipCollector:
    """Accumulates unique clips from feed responses up to a limit.

    ``active`` gates collection so responses arriving while the page is not on
    the target feed (e.g. leftover home-feed requests right after login) are
    ignored. ``already_have`` seeds the de-dup set so clips already on disk are
    skipped.
    """

    def __init__(
        self,
        platform: Platform,
        quality: Quality,
        limit: int,
        on_clip: Callable[[Clip], None],
        active: Optional[Callable[[], bool]] = None,
        already_have: Optional[Set[str]] = None,
    ) -> None:
        self._platform = platform
        self._quality = quality
        self._limit = limit
        self._on_clip = on_clip
        self._active = active or (lambda: True)
        self._seen: Set[str] = set(already_have or ())
        self.clips: list[Clip] = []

    @property
    def full(self) -> bool:
        return len(self.clips) >= self._limit

    def handle_response(self, response: Response) -> None:
        if self.full or not self._active() or not self._looks_like_api_json(response):
            return
        try:
            payload = response.json()
        except Exception:  # non-JSON body, truncated stream, navigation race
            return
        for clip in self._platform.find_clips(payload, self._quality):
            if self.full:
                return
            if clip.ident in self._seen:
                continue
            self._seen.add(clip.ident)
            self.clips.append(clip)
            self._on_clip(clip)

    def _looks_like_api_json(self, response: Response) -> bool:
        if self._platform.host not in response.url or response.status != 200:
            return False
        headers = response.headers
        if "application/json" not in headers.get("content-type", ""):
            return False
        try:
            length = int(headers.get("content-length", 0))
        except ValueError:
            return False
        return length <= _MAX_JSON_BYTES


def _fresh_feed_page(context: BrowserContext) -> Page:
    # A fresh page keeps traffic from previously opened pages (a home feed
    # right after login, most notably) away from the collector; leftovers are
    # closed so they stop loading their own feeds in the background.
    page = context.new_page()
    for other in list(context.pages):
        if other is not page:
            other.close()
    return page


def collect(
    context: BrowserContext,
    platform: Platform,
    quality: Quality,
    count: int,
    on_clip: Callable[[Clip], None],
    on_progress: Optional[Callable[[int], None]] = None,
    target: Optional[str] = None,
    already_have: Optional[Set[str]] = None,
    stall_timeout_s: float = _DEFAULT_STALL_TIMEOUT_S,
) -> list[Clip]:
    """Scroll ``platform``'s feed until ``count`` unique clips are collected.

    Each clip is passed to ``on_clip`` as soon as it is discovered. Raises
    :class:`ExtractionError` if the feed stops yielding new clips for
    ``stall_timeout_s`` seconds before the target is reached.
    """
    # The page must exist before the collector so the response handler's
    # ``active`` check can read its URL the moment navigation starts firing.
    page = _fresh_feed_page(context)
    collector = ClipCollector(
        platform,
        quality,
        count,
        on_clip,
        active=lambda: platform.is_on_feed(_current_url(page)),
        already_have=already_have,
    )
    page.on("response", collector.handle_response)
    page.goto(platform.feed_url(target), wait_until="domcontentloaded")
    if "/accounts/login" in page.url or "/login" in page.url:
        raise NotLoggedInError(
            f"{platform.label} sent us to the login page — your saved session "
            "has expired. Run again with --headed and sign in."
        )

    viewport = page.viewport_size or {"width": 1280, "height": 900}
    page.mouse.move(viewport["width"] / 2, viewport["height"] / 2)

    last_progress = 0
    last_new_clip_at = time.monotonic()
    while not collector.full:
        # Wheel gestures advance snap-scrolled feeds without needing keyboard
        # focus (ArrowDown is ignored until an item is focused).
        page.mouse.wheel(0, viewport["height"])
        page.wait_for_timeout(int(_SCROLL_PAUSE_S * 1000))

        found = len(collector.clips)
        if found > last_progress:
            last_progress = found
            last_new_clip_at = time.monotonic()
            if on_progress:
                on_progress(found)
        elif time.monotonic() - last_new_clip_at > stall_timeout_s:
            if found:
                break  # partial result beats an error deep into a session
            raise ExtractionError(
                f"The {platform.label} feed loaded but yielded no downloadable "
                f"{platform.noun}s — the site may have changed its API or is "
                "showing a checkpoint page. Try again with --headed to watch."
            )
    return collector.clips


def _current_url(page: Page) -> str:
    try:
        return page.url
    except Exception:  # page navigating/closed mid-check
        return ""
