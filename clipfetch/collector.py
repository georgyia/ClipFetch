"""Scroll a platform's feed and harvest clips from its API responses.

This is platform-agnostic: it drives the browser and watches network traffic,
delegating "is this a feed response?" and "what clips are in it?" to the
:class:`~clipfetch.platforms.base.Platform`. New clips are reported through a
callback the moment they are found, so downloads can start while scrolling
continues.
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

from playwright.sync_api import BrowserContext, Page, Response

from clipfetch.errors import ExtractionError, NotLoggedInError
from clipfetch.library import FilterDecision
from clipfetch.model import Clip, Quality
from clipfetch.platforms.base import Platform

_SCROLL_PAUSE_S = 0.6
_MAX_JSON_BYTES = 8 * 1024 * 1024
_DEFAULT_STALL_TIMEOUT_S = 45


@dataclass
class SelectionStats:
    scanned: int = 0
    accepted: int = 0
    rejected: int = 0
    unknown_required_metadata: int = 0
    rejected_by: Counter[str] = field(default_factory=Counter)
    stopped_by_scan_limit: bool = False


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
        active: Callable[[], bool] | None = None,
        already_have: set[str] | None = None,
        scan_limit: int | None = None,
        selector: Callable[[Clip], FilterDecision] | None = None,
        stats: SelectionStats | None = None,
    ) -> None:
        self._platform = platform
        self._quality = quality
        self._limit = limit
        self._on_clip = on_clip
        self._active = active or (lambda: True)
        self._seen: set[str] = set(already_have or ())
        self._scan_limit = scan_limit or limit
        self._selector = selector
        self.stats = stats or SelectionStats()
        self.clips: list[Clip] = []

    @property
    def full(self) -> bool:
        reached_scan_limit = self.stats.scanned >= self._scan_limit
        if reached_scan_limit and len(self.clips) < self._limit:
            self.stats.stopped_by_scan_limit = True
        return len(self.clips) >= self._limit or reached_scan_limit

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
            self.stats.scanned += 1
            decision = self._selector(clip) if self._selector else FilterDecision(True, False)
            if not decision.matches:
                self.stats.rejected += 1
                self.stats.unknown_required_metadata += int(decision.unknown_required_metadata)
                self.stats.rejected_by.update(decision.rejected_by)
                continue
            self.clips.append(clip)
            self.stats.accepted += 1
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
    on_progress: Callable[[int], None] | None = None,
    target: str | None = None,
    already_have: set[str] | None = None,
    stall_timeout_s: float = _DEFAULT_STALL_TIMEOUT_S,
    scan_limit: int | None = None,
    selector: Callable[[Clip], FilterDecision] | None = None,
    selection_stats: SelectionStats | None = None,
) -> list[Clip]:
    """Scroll ``platform``'s feed until ``count`` unique clips are collected.

    Each clip is passed to ``on_clip`` as soon as it is discovered. Raises
    :class:`ExtractionError` if the feed stops yielding new clips for
    ``stall_timeout_s`` seconds before the target is reached.
    """
    # Account (@user) mode may need a bespoke strategy; let the platform take
    # over if it provides one, otherwise fall through to feed scrolling.
    effective_scan_limit = scan_limit or count
    stats = selection_stats or SelectionStats()
    if target:
        accepted: list[Clip] = []

        class EnoughAccepted(Exception):
            pass

        def select_target(clip: Clip) -> None:
            stats.scanned += 1
            decision = selector(clip) if selector else FilterDecision(True, False)
            if decision.matches:
                accepted.append(clip)
                stats.accepted += 1
                on_clip(clip)
                if len(accepted) >= count:
                    raise EnoughAccepted
            else:
                stats.rejected += 1
                stats.unknown_required_metadata += int(decision.unknown_required_metadata)
                stats.rejected_by.update(decision.rejected_by)

        try:
            clips = platform.collect_target(
                context,
                target,
                quality,
                effective_scan_limit,
                select_target,
                already_have or set(),
            )
        except EnoughAccepted:
            clips = accepted
        if clips is not None:
            stats.stopped_by_scan_limit = (
                len(accepted) < count and stats.scanned >= effective_scan_limit
            )
            if on_progress:
                on_progress(len(accepted))
            return accepted

    # The page must exist before the collector so the response handler's
    # ``active`` check can read its URL the moment navigation starts firing.
    page = _fresh_feed_page(context)
    collector = ClipCollector(
        platform,
        quality,
        count,
        on_clip,
        active=lambda: platform.is_on_feed(_current_url(page), target),
        already_have=already_have,
        scan_limit=effective_scan_limit,
        selector=selector,
        stats=stats,
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
        # Wheel gestures advance snap-scrolled feeds (the vertical /reels/
        # player) without needing keyboard focus; the window scroll triggers
        # infinite-scroll pagination on profile grids (@account mode). Doing
        # both covers either layout.
        page.mouse.wheel(0, viewport["height"])
        try:
            page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        except Exception:  # page navigating/closed mid-scroll
            pass
        page.wait_for_timeout(int(_SCROLL_PAUSE_S * 1000))

        found = len(collector.clips)
        scanned = collector.stats.scanned
        if scanned > last_progress:
            last_progress = scanned
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
