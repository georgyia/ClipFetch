"""Poster generation: extract a representative frame for a clip, cached on disk.

Posters are a *gradual* enrichment. Until one is generated the API serves a deterministic SVG
placeholder; once :func:`generate_poster` has run, the real frame is served instead. Generation is
best-effort and never fatal: if ``ffmpeg`` is unavailable the result is ``unavailable`` and the
placeholder keeps showing; a failure leaves no partial file behind.

Posters live under the library's device-local cache (``.clipfetch/posters``) and are addressed only
by platform + clip id — no path from here ever reaches a client.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from clipfetch.catalog import CATALOG_DIR, Catalog, CatalogError

POSTER_DIR = f"{CATALOG_DIR}/posters"
#: Representative frame: seek this far in, clamped below the clip's duration when known.
_DEFAULT_SEEK_SECONDS = 1.0
_POSTER_WIDTH = 540

STATUS_OK = "ok"
STATUS_EXISTS = "exists"
STATUS_UNAVAILABLE = "unavailable"
STATUS_ERROR = "error"


@dataclass(frozen=True)
class PosterResult:
    status: str
    path: Path | None = None
    error: str | None = None


def poster_path(root: Path, platform: str, clip_id: str) -> Path:
    """Device-local cache path for a clip's generated poster."""
    return root / POSTER_DIR / platform / f"{clip_id}.jpg"


def find_ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def _seek_for(duration: float | None) -> float:
    if duration is not None and duration > 0:
        return min(_DEFAULT_SEEK_SECONDS, max(0.0, duration / 2))
    return _DEFAULT_SEEK_SECONDS


def generate_poster(
    root: Path,
    platform: str,
    clip_id: str,
    *,
    ffmpeg: str | None = None,
    force: bool = False,
) -> PosterResult:
    """Extract a representative frame to the poster cache, returning what happened. Never raises."""
    with Catalog.open(root) as catalog:
        record = catalog.get(platform, clip_id)
        if record is None:
            raise CatalogError(f"unknown clip: {platform}/{clip_id}")
        duration = record.duration_seconds
    media = root / record.relative_path
    if not media.is_file():
        return PosterResult(STATUS_ERROR, error="media file is missing")

    destination = poster_path(root, platform, clip_id)
    if destination.is_file() and not force:
        return PosterResult(STATUS_EXISTS, path=destination)

    binary = ffmpeg if ffmpeg is not None else find_ffmpeg()
    if binary is None:
        return PosterResult(STATUS_UNAVAILABLE, error="ffmpeg is not installed")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(".tmp.jpg")
    try:
        subprocess.run(
            [binary, "-y", "-ss", f"{_seek_for(duration):.2f}", "-i", str(media),
             "-frames:v", "1", "-q:v", "3", "-vf", f"scale={_POSTER_WIDTH}:-2", str(temp)],
            capture_output=True,
            timeout=60,
            check=True,
        )
    except (subprocess.SubprocessError, OSError):
        temp.unlink(missing_ok=True)
        return PosterResult(STATUS_ERROR, error="could not generate poster")

    if not temp.is_file() or temp.stat().st_size == 0:
        temp.unlink(missing_ok=True)
        return PosterResult(STATUS_ERROR, error="poster frame was empty")
    temp.replace(destination)
    return PosterResult(STATUS_OK, path=destination)
