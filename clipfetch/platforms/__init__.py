"""Registry of the short-video platforms ClipFetch can download from."""

from __future__ import annotations

from clipfetch.platforms.base import Platform
from clipfetch.platforms.instagram import Instagram
from clipfetch.platforms.tiktok import TikTok

# Order defines CLI help/priority; each is exposed as its own -<flag> option.
#
# YouTubeShorts (clipfetch/platforms/youtube.py) is intentionally NOT registered
# yet: YouTube's Shorts feed ciphers its stream URLs (each needs a signature
# computed by YouTube's player JavaScript, the way yt-dlp does it), so no
# downloadable URL can be extracted without a JS interpreter — outside this
# project's "browser-driver-only" constraint. The extraction logic is kept and
# unit-tested against player responses so it can be wired up if that changes.
ALL: list[Platform] = [Instagram(), TikTok()]

BY_FLAG = {platform.flag: platform for platform in ALL}
BY_KEY = {platform.key: platform for platform in ALL}


def get(flag: str) -> Platform:
    return BY_FLAG[flag]
