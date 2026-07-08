"""TikTok For You feed platform (experimental).

TikTok's web feed loads items through JSON responses (``/api/recommend/…``)
whose items carry an ``id`` and a ``video`` object with one or more playable
URLs. The video CDN rejects requests without a tiktok.com ``Referer``, so
clips carry one. Downloads may still fail when a URL is tied to the browser
session — TikTok is best-effort.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from clipfetch.model import Clip, Quality
from clipfetch.platforms.base import Platform

_HOME = "https://www.tiktok.com/"


class TikTok(Platform):
    key = "tiktok"
    label = "TikTok"
    flag = "tiktoks"
    noun = "tiktok"
    host = "tiktok.com"
    login_url = _HOME + "login"
    session_cookie = None  # the For You feed works without an enforced login
    supports_target = True
    needs_browser_download = True  # signed URLs are bound to the browser session
    experimental = True  # extraction is solid; TikTok anti-bot often blocks downloads

    def feed_url(self, target: str | None = None) -> str:
        if target:
            return f"{_HOME}@{target.lstrip('@')}"
        return _HOME + "foryou"

    def is_on_feed(self, url: str, target: str | None = None) -> bool:
        return self.host in url and "/login" not in url

    def find_clips(self, payload: Any, quality: Quality) -> Iterator[Clip]:
        yield from self._walk(payload, quality)

    def _walk(self, node: Any, quality: Quality) -> Iterator[Clip]:
        if isinstance(node, dict):
            ident = node.get("id")
            video = node.get("video")
            if isinstance(ident, str) and ident and isinstance(video, dict):
                url = self._pick_url(video, quality)
                if url:
                    author = self._author(node)
                    yield Clip(
                        self.key,
                        ident=ident,
                        video_url=url,
                        referer=_HOME,
                        url=f"{_HOME}@{author}/video/{ident}" if author else None,
                        author=author,
                        caption=node.get("desc") if isinstance(node.get("desc"), str) else None,
                        likes=self._likes(node),
                    )
                    return
            for value in node.values():
                yield from self._walk(value, quality)
        elif isinstance(node, list):
            for item in node:
                yield from self._walk(item, quality)

    @staticmethod
    def _author(node: dict) -> str | None:
        author = node.get("author")
        if isinstance(author, dict) and isinstance(author.get("uniqueId"), str):
            return author["uniqueId"]
        if isinstance(author, str) and author:  # some payloads inline the handle
            return author
        return None

    @staticmethod
    def _likes(node: dict) -> int | None:
        stats = node.get("stats")
        if isinstance(stats, dict):
            likes = stats.get("diggCount")
            if isinstance(likes, int) and not isinstance(likes, bool):
                return likes
        return None

    @staticmethod
    def _pick_url(video: dict, quality: Quality) -> str | None:
        # Preferred: bitrateInfo carries several renditions with a bitrate.
        renditions = []
        for entry in video.get("bitrateInfo") or []:
            if not isinstance(entry, dict):
                continue
            play = entry.get("PlayAddr") or {}
            urls = play.get("UrlList") or []
            if urls:
                renditions.append((entry.get("Bitrate") or 0, urls[-1]))
        if renditions:
            renditions.sort(key=lambda r: r[0])  # low → high bitrate
            return quality.choose([url for _, url in renditions])
        # Fallback: a single direct URL.
        for field in ("playAddr", "downloadAddr"):
            url = video.get(field)
            if isinstance(url, str) and url:
                return url
        return None
