"""Instagram Reels platform.

Instagram loads feeds through JSON API responses whose media items carry a
``code`` (shortcode) and ``video_versions`` (direct CDN video URLs). Endpoint
paths change often, so rather than hardcode them we walk every JSON payload
for anything shaped like a video item.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from clipfetch.model import Clip, Quality
from clipfetch.platforms.base import Platform

_HOME = "https://www.instagram.com/"
_SHORTCODE_HREF = re.compile(r"/reel/([A-Za-z0-9_-]+)")
_PERMALINK_TIMEOUT_MS = 8000


class Instagram(Platform):
    key = "instagram"
    label = "Instagram"
    flag = "reels"
    noun = "reel"
    host = "instagram.com"
    login_url = _HOME + "accounts/login/"
    session_cookie = "sessionid"
    supports_target = True

    def feed_url(self, target: str | None = None) -> str:
        if target:
            return f"{_HOME}{target.lstrip('@')}/reels/"
        return _HOME + "reels/"

    def is_on_feed(self, url: str, target: str | None = None) -> bool:
        return url.startswith(_HOME + "reels/")

    def find_clips(self, payload: Any, quality: Quality) -> Iterator[Clip]:
        yield from self._walk(payload, quality)

    def collect_target(self, context, target, quality, count, on_clip, already_have):
        """Download one account's reels.

        A profile's reels grid only lists thumbnails, so we harvest reel
        shortcodes from the grid (scrolling to load more) and then open each
        reel's permalink, where Instagram serves the playable ``video_versions``
        that :meth:`find_clips` extracts.
        """
        user = target.lstrip("@")
        page = context.new_page()
        clips_by_code: dict[str, Clip] = {}

        def capture(response) -> None:
            try:
                if self.host in response.url and "application/json" in \
                        response.headers.get("content-type", ""):
                    for clip in self.find_clips(response.json(), quality):
                        clips_by_code.setdefault(clip.ident, clip)
            except Exception:
                pass

        page.on("response", capture)
        page.goto(f"{_HOME}{user}/reels/", wait_until="domcontentloaded")
        if "/accounts/login" in page.url:
            from clipfetch.errors import NotLoggedInError

            raise NotLoggedInError(
                "Instagram sent us to the login page — run with --headed and sign in."
            )

        codes = self._harvest_shortcodes(page, count, already_have)
        clips: list[Clip] = []
        for code in codes:
            if len(clips) >= count:
                break
            clip = clips_by_code.get(code) or self._resolve_permalink(page, code, clips_by_code)
            if clip:
                clips.append(clip)
                on_clip(clip)
        return clips

    def _harvest_shortcodes(self, page, count, already_have) -> list[str]:
        """Scroll the profile grid collecting unique reel shortcodes."""
        seen = set(already_have)
        ordered: list[str] = []
        stalls = 0
        while len(ordered) < count and stalls < 5:
            hrefs = page.eval_on_selector_all(
                "a[href*='/reel/']", "els => els.map(e => e.getAttribute('href'))"
            )
            before = len(ordered)
            for href in hrefs:
                match = _SHORTCODE_HREF.search(href or "")
                if match and match.group(1) not in seen:
                    seen.add(match.group(1))
                    ordered.append(match.group(1))
            stalls = 0 if len(ordered) > before else stalls + 1
            page.mouse.wheel(0, 2000)
            page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            page.wait_for_timeout(900)
        return ordered

    def _resolve_permalink(self, page, code, clips_by_code) -> Clip | None:
        """Open a reel permalink so its playable clip is captured, then return it."""
        page.goto(f"{_HOME}reel/{code}/", wait_until="domcontentloaded")
        page.wait_for_timeout(300)
        deadline = _PERMALINK_TIMEOUT_MS
        while code not in clips_by_code and deadline > 0:
            page.wait_for_timeout(200)
            deadline -= 200
        return clips_by_code.get(code)

    def _walk(self, node: Any, quality: Quality) -> Iterator[Clip]:
        if isinstance(node, dict):
            code = node.get("code")
            url = self._pick_url(node.get("video_versions"), quality)
            if isinstance(code, str) and code and url:
                yield Clip(
                    self.key,
                    ident=code,
                    video_url=url,
                    url=f"{_HOME}reel/{code}/",
                    author=self._author(node),
                    caption=self._caption(node),
                    likes=self._likes(node),
                )
                return  # a matched media item holds no further items
            for value in node.values():
                yield from self._walk(value, quality)
        elif isinstance(node, list):
            for item in node:
                yield from self._walk(item, quality)

    @staticmethod
    def _author(node: dict) -> str | None:
        for key in ("user", "owner"):
            user = node.get(key)
            if isinstance(user, dict) and isinstance(user.get("username"), str):
                return user["username"]
        return None

    @staticmethod
    def _caption(node: dict) -> str | None:
        caption = node.get("caption")
        if isinstance(caption, dict) and isinstance(caption.get("text"), str):
            return caption["text"]
        return None

    @staticmethod
    def _likes(node: dict) -> int | None:
        likes = node.get("like_count")
        return likes if isinstance(likes, int) and not isinstance(likes, bool) else None

    @staticmethod
    def _pick_url(versions: Any, quality: Quality) -> str | None:
        if not isinstance(versions, list):
            return None
        candidates = [v for v in versions if isinstance(v, dict) and v.get("url")]
        if not candidates:
            return None
        candidates.sort(key=lambda v: v.get("width") or 0)  # low → high
        return quality.choose(candidates)["url"]
