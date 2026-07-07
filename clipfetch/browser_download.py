"""Download clips through the browser context instead of plain urllib.

Some platforms (TikTok) hand out signed video URLs that are bound to the
browser's fingerprint and cookies: a raw urllib request just gets a captcha
page back. Fetching them with Playwright's request API — which reuses the
live session — returns the real bytes. This runs sequentially on the main
thread because the Playwright sync API is not thread-safe.
"""

from __future__ import annotations

from pathlib import Path

from clipfetch.downloader import DownloadResult, filename_for
from clipfetch.model import Clip
from clipfetch.ui import Console, human_size

_TIMEOUT_MS = 60_000
_ATTEMPTS = 3
_BACKOFF_MS = 1500


def _fetch_once(context, clip: Clip) -> bytes:
    headers = {"Range": "bytes=0-"}  # the video CDN serves bytes only for ranged reads
    if clip.referer:
        headers["Referer"] = clip.referer
    response = context.request.get(clip.video_url, headers=headers, timeout=_TIMEOUT_MS)
    if response.status >= 400:
        raise RuntimeError(f"HTTP {response.status}")
    body = response.body()
    if body[:1] in (b"<", b"{"):  # HTML/JSON = a soft block/captcha page, not video
        raise RuntimeError("blocked (anti-bot page)")
    return body


def _fetch(context, clip: Clip) -> bytes:
    """Fetch a clip, retrying the platform's intermittent soft blocks."""
    last: Exception = RuntimeError("no attempt made")
    for attempt in range(_ATTEMPTS):
        try:
            return _fetch_once(context, clip)
        except Exception as err:
            last = err
            if attempt + 1 < _ATTEMPTS:
                _sleep(context, _BACKOFF_MS)
    raise last


def _sleep(context, ms: int) -> None:
    pages = context.pages
    if pages:
        pages[0].wait_for_timeout(ms)


def download_all(
    context, clips: list[Clip], out_dir: Path, noun: str, console: Console
) -> list[DownloadResult]:
    """Download each clip in turn via the browser session. Returns results."""
    results: list[DownloadResult] = []
    for index, clip in enumerate(clips, start=1):
        filename = filename_for(noun, index, clip)
        target = out_dir / filename
        if target.exists() and target.stat().st_size > 0:
            size = target.stat().st_size
            console.dim(f"  [{index}/{len(clips)}] {filename} — already have")
            results.append(DownloadResult(clip, target, size, skipped=True))
            continue
        try:
            body = _fetch(context, clip)
            target.write_bytes(body)
            console.dim(f"  [{index}/{len(clips)}] {filename} — {human_size(len(body))}")
            results.append(DownloadResult(clip, target, len(body)))
        except Exception as err:
            console.error(f"  [{index}/{len(clips)}] {filename} — {err}")
            results.append(DownloadResult(clip, None, 0, error=str(err)))
    return results
