"""Instagram Reels platform.

Instagram loads feeds through JSON API responses whose media items carry a
``code`` (shortcode) and ``video_versions`` (direct CDN video URLs). Endpoint
paths change often, so rather than hardcode them we walk every JSON payload
for anything shaped like a video item.
"""

from __future__ import annotations

from typing import Any, Iterator, Optional

from clipfetch.model import Clip, Quality
from clipfetch.platforms.base import Platform

_HOME = "https://www.instagram.com/"


class Instagram(Platform):
    key = "instagram"
    label = "Instagram"
    flag = "reels"
    noun = "reel"
    host = "instagram.com"
    login_url = _HOME + "accounts/login/"
    session_cookie = "sessionid"
    supports_target = True

    def feed_url(self, target: Optional[str] = None) -> str:
        if target:
            return f"{_HOME}{target.lstrip('@')}/reels/"
        return _HOME + "reels/"

    def find_clips(self, payload: Any, quality: Quality) -> Iterator[Clip]:
        yield from self._walk(payload, quality)

    def _walk(self, node: Any, quality: Quality) -> Iterator[Clip]:
        if isinstance(node, dict):
            code = node.get("code")
            url = self._pick_url(node.get("video_versions"), quality)
            if isinstance(code, str) and code and url:
                yield Clip(self.key, ident=code, video_url=url)
                return  # a matched media item holds no further items
            for value in node.values():
                yield from self._walk(value, quality)
        elif isinstance(node, list):
            for item in node:
                yield from self._walk(item, quality)

    @staticmethod
    def _pick_url(versions: Any, quality: Quality) -> Optional[str]:
        if not isinstance(versions, list):
            return None
        candidates = [v for v in versions if isinstance(v, dict) and v.get("url")]
        if not candidates:
            return None
        candidates.sort(key=lambda v: v.get("width") or 0)  # low → high
        return quality.choose(candidates)["url"]
