"""Registry of the short-video platforms ClipFetch can download from."""

from __future__ import annotations

from clipfetch.platforms.base import Platform
from clipfetch.platforms.instagram import Instagram
from clipfetch.platforms.tiktok import TikTok

# Order defines CLI help/priority; each is exposed as its own -<flag> option.
ALL: list[Platform] = [Instagram(), TikTok()]

BY_FLAG = {platform.flag: platform for platform in ALL}
BY_KEY = {platform.key: platform for platform in ALL}


def get(flag: str) -> Platform:
    return BY_FLAG[flag]
