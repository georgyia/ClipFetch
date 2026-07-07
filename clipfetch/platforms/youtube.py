"""YouTube Shorts platform (NOT REGISTERED — see below).

This module is a foundation, not a working source: it is deliberately left out
of ``clipfetch.platforms.ALL``. YouTube serves each Short's metadata as a
"player response" containing ``videoDetails`` (the video id) and
``streamingData`` (playable formats). ``find_clips`` correctly extracts a
progressive audio+video URL when YouTube exposes a plain ``url``.

In practice the live Shorts feed never hands one out: the URLs are ciphered
(each needs a signature computed by YouTube's player JavaScript — what yt-dlp
reimplements) and Shorts are typically DASH-only with no progressive format.
Extracting a downloadable URL therefore requires a JS signature interpreter,
which is outside ClipFetch's "browser-driver-only" dependency constraint. The
extraction logic and its tests are kept here so the source can be wired up if
a viable non-ciphered path appears. See GitHub issue #2.
"""

from __future__ import annotations

from typing import Any, Iterator, Optional

from clipfetch.model import Clip, Quality
from clipfetch.platforms.base import Platform

_HOME = "https://www.youtube.com/"


class YouTubeShorts(Platform):
    key = "youtube"
    label = "YouTube Shorts"
    flag = "shorts"
    noun = "short"
    host = "youtube.com"
    login_url = _HOME + "account"
    session_cookie = None  # Shorts are viewable without an enforced login
    supports_target = True
    needs_browser_download = True  # googlevideo URLs are session/range bound
    experimental = True

    def feed_url(self, target: Optional[str] = None) -> str:
        if target:
            return f"{_HOME}@{target.lstrip('@')}/shorts"
        return _HOME + "shorts"

    def is_on_feed(self, url: str, target: Optional[str] = None) -> bool:
        return "youtube.com/shorts" in url or "/shorts" in url

    def find_clips(self, payload: Any, quality: Quality) -> Iterator[Clip]:
        yield from self._walk(payload, quality)

    def _walk(self, node: Any, quality: Quality) -> Iterator[Clip]:
        if isinstance(node, dict):
            details = node.get("videoDetails")
            streaming = node.get("streamingData")
            if isinstance(details, dict) and isinstance(streaming, dict):
                ident = details.get("videoId")
                url = self._pick_url(streaming, quality)
                if isinstance(ident, str) and ident and url:
                    yield Clip(self.key, ident=ident, video_url=url, referer=_HOME)
                    return
            for value in node.values():
                yield from self._walk(value, quality)
        elif isinstance(node, list):
            for item in node:
                yield from self._walk(item, quality)

    @staticmethod
    def _pick_url(streaming: dict, quality: Quality) -> Optional[str]:
        # Progressive formats carry audio+video together; only non-ciphered
        # entries expose a direct "url" (ciphered ones need player JS we avoid).
        playable = [
            f
            for f in streaming.get("formats") or []
            if isinstance(f, dict)
            and f.get("url")
            and (f.get("mimeType") or "").startswith("video/mp4")
        ]
        if not playable:
            return None
        playable.sort(key=lambda f: f.get("height") or f.get("bitrate") or 0)
        return quality.choose(playable)["url"]
