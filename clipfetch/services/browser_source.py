"""Real download source: drive the browser stack to fetch reels for a ClipFetch Watch job.

This is the production counterpart to the offline ``FakeSourceProvider``. It reuses the exact stack
the CLI uses — a signed-in persistent browser profile (``session``), feed harvesting
(``collector``), and a plain-HTTPS download — but runs unattended inside the worker: it never opens
an interactive sign-in window, streams each video to a temp file (no whole video in memory), and
turns stack failures into user-safe :class:`IngestError` categories the UI can act on.

The browser/collector/download steps are injected so the orchestration, error mapping, and the
download-to-disk path are fully testable offline with fakes; the defaults wire the real stack, which
is only exercised end-to-end behind the opt-in ``integration`` marker (it needs a real sign-in).
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Callable

from clipfetch.model import Clip, Quality
from clipfetch.platforms.base import Platform
from clipfetch.services.ingest_service import IngestError, SourceClip

# Injected seams (defaults wire the real browser stack lazily, so tests never import Playwright).
OpenSession = Callable[[Platform], AbstractContextManager[object]]
HasSession = Callable[[object, Platform], bool]
CookieHeader = Callable[[object, Platform], str]
Harvest = Callable[..., list[Clip]]
Download = Callable[[Clip, Path, dict], None]

_DOWNLOAD_TIMEOUT_S = 60
_CHUNK = 256 * 1024
_RATE_LIMIT_STATUSES = frozenset({403, 429})


class BrowserSourceProvider:
    """A ``SourceProvider`` (see ``ingest_service``) backed by the real browser download stack.

    Collects up to ``count`` clips from ``platform`` (optionally an ``@account`` passed as the
    permalink), downloads each to a temp file, and yields it for the ingest layer to catalogue.
    """

    def __init__(
        self,
        platform: Platform,
        *,
        open_session: OpenSession | None = None,
        has_session: HasSession | None = None,
        cookie_header: CookieHeader | None = None,
        harvest: Harvest | None = None,
        download: Download | None = None,
    ) -> None:
        self._platform = platform
        self._open_session = open_session or _default_open_session
        self._has_session = has_session or _default_has_session
        self._cookie_header = cookie_header or _default_cookie_header
        self._harvest = harvest or _default_harvest
        self._download = download or _default_download

    def fetch(self, permalink: str, count: int, quality: str | None) -> Iterator[SourceClip]:
        target = _target_from(permalink)
        want = _parse_quality(quality)
        with self._open_session(self._platform) as context:
            if not self._has_session(context, self._platform):
                raise IngestError(
                    f"Not signed in to {self._platform.label}. Connect the account first.",
                    code="authentication_required",
                )
            headers = {"Cookie": self._cookie_header(context, self._platform)}
            clips = self._collect(context, want, count, target)
            for clip in clips:
                yield self._download_clip(clip, headers)

    def _collect(
        self, context: object, quality: Quality, count: int, target: str | None
    ) -> list[Clip]:
        from clipfetch.errors import ExtractionError, NotLoggedInError

        try:
            return self._harvest(
                context,
                self._platform,
                quality,
                count,
                on_clip=lambda _clip: None,
                target=target,
            )
        except NotLoggedInError as err:
            raise IngestError(str(err), code="authentication_required") from err
        except ExtractionError as err:
            raise IngestError(
                f"Could not read the {self._platform.label} feed.", code="source_unavailable"
            ) from err

    def _download_clip(self, clip: Clip, headers: dict) -> SourceClip:
        fd, name = tempfile.mkstemp(prefix="clipfetch-dl-", suffix=".mp4")
        os.close(fd)
        tmp = Path(name)
        try:
            self._download(clip, tmp, headers)
        except Exception as err:  # noqa: BLE001 - mapped to a user-safe category below
            tmp.unlink(missing_ok=True)
            status = getattr(err, "code", None) or getattr(err, "status", None)
            category = "rate_limited" if status in _RATE_LIMIT_STATUSES else "source_unavailable"
            raise IngestError(
                f"Could not download {clip.ident} from {self._platform.label}.", code=category
            ) from err
        meta = clip.normalized_metadata()
        return SourceClip(
            clip_id=clip.ident,
            platform=self._platform.key,
            media=None,
            media_path=tmp,
            source_url=clip.url or clip.video_url,
            author=clip.author,
            caption=clip.caption,
            likes=clip.likes,
            views=clip.views,
            duration_seconds=clip.duration_seconds,
            hashtags=meta.hashtags,
        )


def _target_from(permalink: str) -> str | None:
    """A leading ``@handle`` selects single-account mode; anything else means the signed-in feed."""
    value = (permalink or "").strip()
    if value.startswith("@"):
        return value[1:] or None
    return None


def _parse_quality(value: str | None) -> Quality:
    try:
        return Quality(value) if value else Quality.HIGH
    except ValueError:
        return Quality.HIGH


# -- default real-stack seams (imported lazily so unit tests stay Playwright-free) ----------------


def _default_open_session(platform: Platform) -> AbstractContextManager[object]:
    from clipfetch import session

    return session.authenticated_session(platform)


def _default_has_session(context: object, platform: Platform) -> bool:
    from playwright.sync_api import BrowserContext

    from clipfetch import session

    assert isinstance(context, BrowserContext)
    return session.has_session_cookie(context, platform)


def _default_cookie_header(context: object, platform: Platform) -> str:
    from playwright.sync_api import BrowserContext

    from clipfetch import session

    assert isinstance(context, BrowserContext)
    return session.cookie_header(context, platform)


def _default_harvest(
    context: object, platform: Platform, quality: Quality, count: int, **kw
) -> list[Clip]:
    from playwright.sync_api import BrowserContext

    from clipfetch import collector

    assert isinstance(context, BrowserContext)
    return collector.collect(context, platform, quality, count, **kw)


def _default_download(clip: Clip, dest: Path, headers: dict) -> None:
    import urllib.request

    from clipfetch.constants import USER_AGENT

    request_headers = {"User-Agent": USER_AGENT, **headers}
    if clip.referer:
        request_headers["Referer"] = clip.referer
    request = urllib.request.Request(clip.video_url, headers=request_headers)
    with urllib.request.urlopen(request, timeout=_DOWNLOAD_TIMEOUT_S) as response:
        with dest.open("wb") as out:
            while chunk := response.read(_CHUNK):
                out.write(chunk)
