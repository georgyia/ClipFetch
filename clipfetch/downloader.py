"""Parallel clip downloads over plain HTTPS.

The CDN URLs harvested from a feed usually need no browser, so downloads run on
a thread pool with stdlib ``urllib`` while the browser is still scrolling for
more clips (producer/consumer pipeline).
"""

from __future__ import annotations

import itertools
import re
import urllib.error
import urllib.request
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from clipfetch.constants import USER_AGENT
from clipfetch.model import Clip
from clipfetch.ui import MultiProgress

_CHUNK_SIZE = 256 * 1024
_REQUEST_TIMEOUT_S = 60
_SAFE_IDENT = re.compile(r"[^A-Za-z0-9_-]")


@dataclass(frozen=True)
class DownloadResult:
    """Outcome of one clip download."""

    clip: Clip
    path: Optional[Path]
    size: int
    error: Optional[str] = None
    skipped: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None


def filename_for(noun: str, index: int, clip: Clip) -> str:
    """Deterministic filename so re-runs can recognise existing downloads."""
    ident = _SAFE_IDENT.sub("", clip.ident) or "clip"
    return f"{noun}_{index:03d}_{ident}.mp4"


class DownloadPool:
    """Downloads clips on worker threads as they are discovered.

    ``submit()`` may be called from the browser thread while downloads are
    already running; ``wait()`` blocks until every submitted clip finished.
    """

    def __init__(
        self, out_dir: Path, noun: str, workers: int, progress: MultiProgress
    ) -> None:
        self._out_dir = out_dir
        self._noun = noun
        self._progress = progress
        self._executor = ThreadPoolExecutor(workers, thread_name_prefix="download")
        self._futures: list[Future[DownloadResult]] = []
        self._indexes = itertools.count(1)

    def submit(self, clip: Clip) -> None:
        index = next(self._indexes)
        self._futures.append(self._executor.submit(self._download, index, clip))

    def wait(self) -> list[DownloadResult]:
        results = [future.result() for future in self._futures]
        self._executor.shutdown()
        return results

    def _download(self, index: int, clip: Clip) -> DownloadResult:
        filename = filename_for(self._noun, index, clip)
        target = self._out_dir / filename
        if target.exists() and target.stat().st_size > 0:
            self._progress.add(index, filename, total=target.stat().st_size)
            self._progress.update(index, target.stat().st_size)
            self._progress.finish(index)
            return DownloadResult(clip, path=target, size=target.stat().st_size, skipped=True)

        self._progress.add(index, filename)
        partial = target.with_suffix(".part")
        try:
            size = self._fetch(index, clip, partial)
            partial.replace(target)
        except (urllib.error.URLError, OSError, ValueError) as err:
            partial.unlink(missing_ok=True)
            self._progress.finish(index, failed=True)
            return DownloadResult(clip, path=None, size=0, error=str(err))
        self._progress.finish(index)
        return DownloadResult(clip, path=target, size=size)

    def _fetch(self, index: int, clip: Clip, destination: Path) -> int:
        headers = {"User-Agent": USER_AGENT}
        if clip.referer:
            headers["Referer"] = clip.referer
        request = urllib.request.Request(clip.video_url, headers=headers)
        received = 0
        with urllib.request.urlopen(request, timeout=_REQUEST_TIMEOUT_S) as response:
            total = int(response.headers.get("Content-Length") or 0)
            with destination.open("wb") as file:
                while chunk := response.read(_CHUNK_SIZE):
                    file.write(chunk)
                    received += len(chunk)
                    self._progress.update(index, received, total or None)
        return received
