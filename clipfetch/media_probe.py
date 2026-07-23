"""Technical media probing.

Reads a downloaded video's duration, dimensions, codecs, bitrate, and container via ``ffprobe`` when
it is available, and decides whether the file is directly browser-playable. Probing is best-effort
and never fatal: if ``ffprobe`` is missing the result is ``unknown``; if a specific value cannot be
determined it stays ``None``. The JSON parsing is a pure function so it can be tested without the
binary.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

STATUS_OK = "ok"
STATUS_UNKNOWN = "unknown"
STATUS_ERROR = "error"

# Codecs/containers a browser can play from an <video src> without transcoding.
_BROWSER_VIDEO = {"h264", "avc1", "vp8", "vp9", "av1"}
_BROWSER_AUDIO = {"aac", "mp3", "opus", "vorbis", None}
_BROWSER_CONTAINER = {"mp4", "mov", "m4v", "webm", "isom"}


@dataclass(frozen=True)
class MediaProbe:
    status: str
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    bitrate: int | None = None
    container: str | None = None
    compatible: bool | None = None
    error: str | None = None


def find_ffprobe() -> str | None:
    return shutil.which("ffprobe")


def _first_container(format_name: str | None) -> str | None:
    if not format_name:
        return None
    return format_name.split(",")[0].strip() or None


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compatible(video: str | None, audio: str | None, container: str | None) -> bool | None:
    """Browser playability, or ``None`` when the codecs/container are unknown."""
    if video is None and container is None:
        return None
    if video is not None and video not in _BROWSER_VIDEO:
        return False
    if audio is not None and audio not in _BROWSER_AUDIO:
        return False
    if container is not None and container not in _BROWSER_CONTAINER:
        return False
    return True


def parse_ffprobe(payload: dict[str, Any]) -> MediaProbe:
    """Build a :class:`MediaProbe` from a parsed ``ffprobe -show_format -show_streams`` document."""
    fmt = payload.get("format", {}) if isinstance(payload.get("format"), dict) else {}
    streams = payload.get("streams", [])
    streams = streams if isinstance(streams, list) else []

    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    video_codec = video.get("codec_name") if video else None
    audio_codec = audio.get("codec_name") if audio else None
    container = _first_container(fmt.get("format_name"))

    return MediaProbe(
        status=STATUS_OK,
        duration_seconds=_as_float(fmt.get("duration")),
        width=_as_int(video.get("width")) if video else None,
        height=_as_int(video.get("height")) if video else None,
        video_codec=video_codec,
        audio_codec=audio_codec,
        bitrate=_as_int(fmt.get("bit_rate")),
        container=container,
        compatible=_compatible(video_codec, audio_codec, container),
    )


def probe_file(path: Path, *, ffprobe: str | None = None) -> MediaProbe:
    """Probe ``path``. Returns ``unknown`` if ffprobe is unavailable, ``error`` on failure."""
    if not path.is_file():
        return MediaProbe(status=STATUS_ERROR, error="media file is missing")
    binary = ffprobe if ffprobe is not None else find_ffprobe()
    if binary is None:
        return MediaProbe(status=STATUS_UNKNOWN, error="ffprobe is not installed")
    try:
        completed = subprocess.run(
            [binary, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams",
             str(path)],
            capture_output=True,
            timeout=30,
            check=True,
        )
        payload = json.loads(completed.stdout.decode("utf-8", "replace"))
    except (subprocess.SubprocessError, OSError, ValueError):
        # Sanitized: never surface the binary's stderr or a traceback.
        return MediaProbe(status=STATUS_ERROR, error="could not probe media")
    return parse_ffprobe(payload)
