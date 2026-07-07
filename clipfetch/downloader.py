"""Parallel reel downloads over plain HTTPS.

The CDN URLs harvested from the feed need no browser and no cookies, so
downloads run on a thread pool with stdlib ``urllib`` while the browser is
still scrolling for more reels (producer/consumer pipeline).
"""

from __future__ import annotations

import itertools
import urllib.error
import urllib.request
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from clipfetch.constants import USER_AGENT
from clipfetch.reels import Reel
from clipfetch.ui import MultiProgress

_CHUNK_SIZE = 256 * 1024
_REQUEST_TIMEOUT_S = 60


@dataclass(frozen=True)
class DownloadResult:
    """Outcome of one reel download."""

    reel: Reel
    path: Optional[Path]
    size: int
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


class DownloadPool:
    """Downloads reels on worker threads as they are discovered.

    ``submit()`` may be called from the browser thread while downloads are
    already running; ``wait()`` blocks until every submitted reel finished.
    """

    def __init__(self, out_dir: Path, workers: int, progress: MultiProgress) -> None:
        self._out_dir = out_dir
        self._progress = progress
        self._executor = ThreadPoolExecutor(workers, thread_name_prefix="download")
        self._futures: list[Future[DownloadResult]] = []
        self._indexes = itertools.count(1)

    def submit(self, reel: Reel) -> None:
        index = next(self._indexes)
        self._futures.append(self._executor.submit(self._download, index, reel))

    def wait(self) -> list[DownloadResult]:
        results = [future.result() for future in self._futures]
        self._executor.shutdown()
        return results

    def _download(self, index: int, reel: Reel) -> DownloadResult:
        filename = f"reel_{index:03d}_{reel.shortcode}.mp4"
        self._progress.add(index, filename)
        target = self._out_dir / filename
        partial = target.with_suffix(".part")
        try:
            size = self._fetch(index, reel.video_url, partial)
            partial.replace(target)
        except (urllib.error.URLError, OSError, ValueError) as err:
            partial.unlink(missing_ok=True)
            self._progress.finish(index, failed=True)
            return DownloadResult(reel, path=None, size=0, error=str(err))
        self._progress.finish(index)
        return DownloadResult(reel, path=target, size=size)

    def _fetch(self, index: int, url: str, destination: Path) -> int:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        received = 0
        with urllib.request.urlopen(request, timeout=_REQUEST_TIMEOUT_S) as response:
            total = int(response.headers.get("Content-Length") or 0)
            with destination.open("wb") as file:
                while chunk := response.read(_CHUNK_SIZE):
                    file.write(chunk)
                    received += len(chunk)
                    self._progress.update(index, received, total or None)
        return received
