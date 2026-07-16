"""Parallel clip downloads over plain HTTPS.

The CDN URLs harvested from a feed usually need no browser, so downloads run on
a thread pool with stdlib ``urllib`` while the browser is still scrolling for
more clips (producer/consumer pipeline).
"""

from __future__ import annotations

import http.client
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
_CONTENT_RANGE = re.compile(r"bytes (\d+)-(\d+)/(\d+|\*)")


@dataclass(frozen=True)
class DownloadResult:
    """Outcome of one clip download."""

    clip: Clip
    path: Path | None
    size: int
    error: str | None = None
    skipped: bool = False
    catalog_error: str | None = None

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
            size = target.stat().st_size
            self._progress.add(index, filename, total=size, done=size)
            self._progress.finish(index)
            if self._metadata:  # an earlier run without --metadata may lack one
                write_sidecar(target, clip)
            catalog_error = self._catalog(target, clip)
            return DownloadResult(
                clip,
                path=target,
                size=target.stat().st_size,
                skipped=True,
                catalog_error=catalog_error,
            )

        partial = self._find_partial(clip) or target.with_suffix(".part")
        # A previous run may have assigned a different numeric prefix before
        # interruption. Keep that stable so its partial can be resumed.
        if partial != target.with_suffix(".part"):
            target = partial.with_suffix(".mp4")
        offset = partial.stat().st_size if partial.exists() else 0
        self._progress.add(index, filename, done=offset)
        try:
            size = self._fetch(index, clip, partial)
            partial.replace(target)
        except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as err:
            # Preserve verified bytes for a later run. CDN URLs can expire, but
            # the next collection supplies a fresh URL for the same clip id.
            self._progress.finish(index, failed=True)
            return DownloadResult(clip, path=None, size=0, error=str(err))
        if self._metadata:
            write_sidecar(target, clip)
        catalog_error = self._catalog(target, clip)
        self._progress.finish(index)
        return DownloadResult(clip, path=target, size=size, catalog_error=catalog_error)

    def _catalog(self, target: Path, clip: Clip) -> str | None:
        """Catalog a usable file without turning catalog errors into download errors."""
        from clipfetch.catalog import CatalogError, record_completed_download

        try:
            record_completed_download(self._out_dir, target, clip)
        except (CatalogError, OSError) as err:
            return str(err)
        return None

    def _find_partial(self, clip: Clip) -> Path | None:
        pattern = f"{self._noun}_*_{safe_ident(clip.ident)}.part"
        candidates = [path for path in self._out_dir.glob(pattern) if path.is_file()]
        if not candidates:
            return None
        # Prefer the copy containing the most reusable data if an old bug or a
        # manual copy left more than one candidate behind.
        return max(candidates, key=lambda path: path.stat().st_size)

    def _fetch(self, index: int, clip: Clip, destination: Path) -> int:
        headers = {"User-Agent": USER_AGENT, **self._extra_headers}
        if clip.referer:
            headers["Referer"] = clip.referer
        offset = destination.stat().st_size if destination.exists() else 0
        if offset:
            headers["Range"] = f"bytes={offset}-"
        request = urllib.request.Request(clip.video_url, headers=headers)
        try:
            response = urllib.request.urlopen(request, timeout=_REQUEST_TIMEOUT_S)
        except urllib.error.HTTPError as error:
            if error.code == 416 and offset:
                remote_size = _unsatisfied_range_size(error.headers.get("Content-Range"))
                if remote_size == offset:
                    self._progress.update(index, offset, offset)
                    return offset
            raise
        with response:
            status = getattr(response, "status", response.getcode())
            content_length = int(response.headers.get("Content-Length") or 0)
            mode = "wb"
            received = 0
            total = content_length
            if offset and status == 206:
                start, complete_size = _parse_content_range(
                    response.headers.get("Content-Range")
                )
                if start != offset:
                    raise ValueError(
                        f"server resumed at byte {start}, expected {offset}"
                    )
                mode = "ab"
                received = offset
                total = complete_size or offset + content_length
                self._progress.update(index, received, total or None)
            # A 200 response ignored Range. Starting over is safe; appending is not.
            with destination.open(mode) as file:
                while chunk := response.read(_CHUNK_SIZE):
                    file.write(chunk)
                    received += len(chunk)
                    self._progress.update(index, received, total or None)
            if total and received != total:
                raise OSError(
                    f"download ended at byte {received}, expected {total}; "
                    "partial file was preserved"
                )
        return received


def _parse_content_range(value: str | None) -> tuple[int, int | None]:
    match = _CONTENT_RANGE.fullmatch(value or "")
    if not match:
        raise ValueError("server returned an invalid Content-Range header")
    start = int(match.group(1))
    total = None if match.group(3) == "*" else int(match.group(3))
    return start, total


def _unsatisfied_range_size(value: str | None) -> int | None:
    match = re.fullmatch(r"bytes \*/(\d+)", value or "")
    return int(match.group(1)) if match else None
