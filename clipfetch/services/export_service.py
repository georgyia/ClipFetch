"""Export a collection or a filtered view as a portable playlist or a stable manifest.

This is the CLI's ``library export`` reachable from the web layer, and it reuses the CLI's exact
serializers (:func:`clipfetch.collections.export_m3u` / :func:`~clipfetch.collections.export_json`)
rather than re-deriving them — an export that disagreed with the CLI's would be worse than none.

Both formats stay **portable**: the M3U carries library-relative paths and the JSON manifest sets
``"library": "."``. Nothing here may introduce an absolute path, which is also why the export is
built from the same ``QueryResult`` the rest of the app pages through.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from clipfetch.collections import export_json, export_m3u, get_collection
from clipfetch.library import ClipFilter, QueryResult, query_selection

#: The formats the API accepts.
EXPORT_FORMATS = ("m3u", "json")

#: Upper bound on an exported set.
#:
#: The serializers build one string, so the response is materialized in memory; a cap keeps that
#: bounded without forking them into streaming variants that could drift from the CLI's output.
#: Five thousand clips is far past any hand-curated collection and still only a few MB of JSON.
MAX_EXPORT_CLIPS = 5000

_MEDIA_TYPES = {"m3u": "audio/x-mpegurl", "json": "application/json"}
_UNSAFE_FILENAME = re.compile(r"[^a-z0-9._-]+")


class ExportError(ValueError):
    """The requested export format is not supported."""


@dataclass(frozen=True)
class Export:
    """A rendered export: its bytes-as-text, its media type, and the name to save it under."""

    body: str
    media_type: str
    filename: str
    clip_count: int
    #: True when the library holds more matches than the export cap allowed.
    truncated: bool


def _render(result: QueryResult, root: Path, *, fmt: str, name: str) -> Export:
    if fmt not in EXPORT_FORMATS:
        raise ExportError(f"format must be one of: {', '.join(EXPORT_FORMATS)}")
    body = export_json(root, result) if fmt == "json" else export_m3u(result)
    return Export(
        body=body,
        media_type=_MEDIA_TYPES[fmt],
        filename=f"{_safe_name(name)}.{fmt}",
        clip_count=len(result.clips),
        truncated=result.matched > len(result.clips),
    )


def export_collection(root: Path, name: str, *, fmt: str, sort: str = "date") -> Export:
    """Export one saved collection — its filter matches and its pinned clips alike."""
    collection = get_collection(root, name)
    result = query_selection(
        root, collection.filters, collection.clips, sort=sort, limit=MAX_EXPORT_CLIPS
    )
    return _render(result, root, fmt=fmt, name=f"clipfetch-{collection.name}")


def export_view(
    root: Path,
    filters: ClipFilter | None = None,
    *,
    fmt: str,
    sort: str = "date",
    name: str = "clips",
) -> Export:
    """Export whatever a filter currently matches, so a filtered view is exportable as it stands."""
    result = query_selection(root, filters or ClipFilter(), sort=sort, limit=MAX_EXPORT_CLIPS)
    return _render(result, root, fmt=fmt, name=f"clipfetch-{name}")


def _safe_name(value: str) -> str:
    """Reduce a name to something safe for a Content-Disposition filename."""
    cleaned = _UNSAFE_FILENAME.sub("-", value.strip().lower()).strip("-")
    return cleaned or "clipfetch-export"
