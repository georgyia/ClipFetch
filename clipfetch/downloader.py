"""Parallel clip downloads over plain HTTPS.

The CDN URLs harvested from a feed usually need no browser, so downloads run on
a thread pool with stdlib ``urllib`` while the browser is still scrolling for
more clips (producer/consumer pipeline).
"""

from __future__ import annotations

import itertools
import json
import re
import urllib.error
import urllib.request
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

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
    path: Path | None
    size: int
    error: str | None = None
    skipped: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None


def filename_for(noun: str, index: int, clip: Clip) -> str:
    """Deterministic filename so re-runs can recognise existing downloads."""
    return f"{noun}_{index:03d}_{safe_ident(clip.ident)}.mp4"


def safe_ident(ident: str) -> str:
    """Filesystem-safe form of a clip id (platform ids are already URL-safe)."""
    return _SAFE_IDENT.sub("", ident) or "clip"


def existing_idents(out_dir: Path, noun: str) -> set[str]:
    """Ids already fully downloaded in ``out_dir`` (``<noun>_<n>_<id>.mp4``)."""
    pattern = re.compile(rf"^{re.escape(noun)}_\d+_(.+)\.mp4$")
    found = set()
    for path in out_dir.glob(f"{noun}_*.mp4"):
        match = pattern.match(path.name)
        if match and path.stat().st_size > 0:
            found.add(match.group(1))
    return found


def write_sidecar(video_path: Path, clip: Clip) -> Path:
    """Write ``clip``'s metadata next to its video as ``<name>.json``.

    Backs the ``--metadata`` flag. Existing sidecars are rewritten: a re-run
    may know more about a clip than the interrupted run that first saved it.
    """
    sidecar = video_path.with_suffix(".json")
    sidecar.write_text(
        json.dumps(clip.metadata(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return sidecar


def clean_partials(out_dir: Path) -> int:
    """Remove leftover ``.part`` files from interrupted runs. Returns the count."""
    removed = 0
    for path in out_dir.glob("*.part"):
        path.unlink(missing_ok=True)
        removed += 1
    return removed


class DownloadPool:
    """Downloads clips on worker threads as they are discovered.

    ``submit()`` may be called from the browser thread while downloads are
    already running; ``wait()`` blocks until every submitted clip finished.
    """

    def __init__(
        self,
        out_dir: Path,
        noun: str,
        workers: int,
        progress: MultiProgress,
        extra_headers: dict | None = None,
        metadata: bool = False,
    ) -> None:
        self._out_dir = out_dir
        self._noun = noun
        self._progress = progress
        self._extra_headers = extra_headers or {}
        self._metadata = metadata
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
            if self._metadata:  # an earlier run without --metadata may lack one
                write_sidecar(target, clip)
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
        if self._metadata:
            write_sidecar(target, clip)
        self._progress.finish(index)
        return DownloadResult(clip, path=target, size=size)

    def _fetch(self, index: int, clip: Clip, destination: Path) -> int:
        headers = {"User-Agent": USER_AGENT, **self._extra_headers}
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
