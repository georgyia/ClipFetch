"""Safe media and poster resolution, addressed only by catalog clip ID.

No endpoint ever accepts a filesystem path. Media is resolved by resolving a clip's stored
*relative* path against the validated library root and confirming the result stays inside that root
(:func:`safe_media_path`), which prevents path traversal. Posters are not generated yet, so a
deterministic neutral placeholder is produced from the clip itself.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from pathlib import Path

from clipfetch.catalog import CatalogRecord

CHUNK_SIZE = 64 * 1024

# Extensions we are willing to serve, mapped to their media types.
MEDIA_TYPES = {
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
}


class MediaError(RuntimeError):
    """The requested media cannot be safely resolved or served."""


def safe_media_path(root: Path, relative_path: str) -> Path:
    """Resolve ``relative_path`` under ``root`` and confirm it does not escape the root."""
    root = root.resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as err:
        raise MediaError("resolved media path escapes the library root") from err
    return candidate


def media_type_for(path: Path) -> str:
    return MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")


def media_etag(size: int, mtime_ns: int) -> str:
    """A stable strong ETag for a local file, derived from its size and mtime."""
    return f'"{size:x}-{mtime_ns:x}"'


def parse_byte_range(header: str, size: int) -> tuple[int, int] | None:
    """Parse a single HTTP Range header into an inclusive ``(start, end)``.

    Returns ``None`` for an unsatisfiable or unsupported range (the caller answers ``416``). Only a
    single range is supported; multi-range requests are treated as unsatisfiable.
    """
    if not header.startswith("bytes=") or size <= 0:
        return None
    spec = header[len("bytes=") :].strip()
    if "," in spec or "-" not in spec:
        return None
    start_text, _, end_text = spec.partition("-")
    try:
        if start_text == "":
            suffix = int(end_text)
            if suffix <= 0:
                return None
            start, end = max(0, size - suffix), size - 1
        else:
            start = int(start_text)
            end = int(end_text) if end_text else size - 1
    except ValueError:
        return None
    if start < 0 or start >= size or end < start:
        return None
    return start, min(end, size - 1)


def file_iterator(path: Path, start: int, end: int, chunk: int = CHUNK_SIZE) -> Iterator[bytes]:
    """Yield ``path`` bytes for the inclusive range ``[start, end]`` without loading it all."""
    remaining = end - start + 1
    with path.open("rb") as handle:
        handle.seek(start)
        while remaining > 0:
            data = handle.read(min(chunk, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


def _poster_label(record: CatalogRecord) -> str:
    for source in (record.author, record.caption, record.clip_id):
        for char in source or "":
            if char.isalnum():
                return char.upper()
    return "?"


def _xml_escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def poster_etag(record: CatalogRecord) -> str:
    digest = hashlib.sha1(record.clip_id.encode("utf-8")).hexdigest()[:16]
    return f'W/"poster-{digest}"'


def poster_placeholder(record: CatalogRecord) -> bytes:
    """Return a deterministic 9:16 SVG placeholder poster for a clip with no generated poster."""
    seed = int(hashlib.sha256(record.clip_id.encode("utf-8")).hexdigest(), 16)
    hue = seed % 360
    label = _xml_escape(_poster_label(record))
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="270" height="480" '
        'viewBox="0 0 270 480" role="img" aria-label="No poster available">'
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="hsl({hue} 55% 22%)"/>'
        f'<stop offset="1" stop-color="hsl({(hue + 40) % 360} 60% 12%)"/>'
        "</linearGradient></defs>"
        '<rect width="270" height="480" fill="url(#g)"/>'
        '<text x="135" y="270" font-family="system-ui, sans-serif" font-size="140" '
        'font-weight="700" fill="rgba(255,255,255,0.82)" text-anchor="middle">'
        f"{label}</text></svg>"
    )
    return svg.encode("utf-8")
