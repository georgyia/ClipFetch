"""Library maintenance: the clips whose media has gone missing, and forgetting their records.

Indexing reconciles *presence* — a file that disappears is marked unavailable, never dropped —
which is the right default, since a moved folder must not cost you everything the library knows.
The consequence is that dead records accumulate silently: they are filtered out of every browse
view, so the only way to meet one is to click it.

This service is the other side of that trade: it lists them, and it forgets the ones that are
genuinely gone. Forgetting removes a catalog row and its derived data. It never deletes media —
and it refuses to run on a clip whose file is present, so it cannot become a delete button by
accident.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clipfetch.catalog import Catalog, CatalogError
from clipfetch.contracts import clip_summary
from clipfetch.library import find_clip, query_missing

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class MaintenanceError(RuntimeError):
    """A maintenance action was refused — e.g. forgetting a clip whose media is still there."""


@dataclass(frozen=True)
class MissingClip:
    """A catalogued clip whose file is absent, plus where it used to live.

    ``relative_path`` is included here although :class:`~clipfetch.contracts.ClipSummary` omits it.
    It is library-relative, never absolute — the same value the M3U and JSON exports already
    carry — and it is the one piece of information that makes this view actionable: it is how you
    find out *which* file to restore.
    """

    clip: dict[str, Any]
    relative_path: str
    file_size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.clip,
            "relative_path": self.relative_path,
            "file_size_bytes": self.file_size_bytes,
        }


@dataclass(frozen=True)
class MissingPage:
    items: tuple[MissingClip, ...]
    total: int
    next_offset: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [item.to_dict() for item in self.items],
            "total": self.total,
            "next_offset": self.next_offset,
        }


@dataclass(frozen=True)
class ForgetReport:
    """What a forget request actually did. ``kept`` names clips whose media was found present."""

    forgotten: tuple[str, ...]
    kept: tuple[str, ...]
    unknown: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "forgotten": list(self.forgotten),
            "kept": list(self.kept),
            "unknown": list(self.unknown),
        }


def list_missing(root: Path, *, limit: int = DEFAULT_LIMIT, offset: int = 0) -> MissingPage:
    """Return a bounded page of clips whose media file is gone, newest first."""
    page_size = max(1, min(limit, MAX_LIMIT))
    start = max(0, offset)
    result = query_missing(root, limit=page_size, offset=start)
    end = start + len(result.clips)
    return MissingPage(
        items=tuple(
            MissingClip(
                clip=clip_summary(record).to_dict(),
                relative_path=record.relative_path,
                file_size_bytes=record.file_size,
            )
            for record in result.clips
        ),
        total=result.matched,
        next_offset=end if end < result.matched else None,
    )


def forget_clips(root: Path, clip_ids: Sequence[str]) -> ForgetReport:
    """Drop the catalog records for clips whose media is missing. Never touches a file.

    A clip whose file is present is *kept*, not forgotten, and reported back as such: this action
    exists to clean up after a deletion that already happened, not to perform one.
    """
    forgotten: list[str] = []
    kept: list[str] = []
    unknown: list[str] = []
    for clip_id in clip_ids:
        try:
            record = find_clip(root, clip_id)
        except CatalogError:
            unknown.append(clip_id)
            continue
        if (root / record.relative_path).is_file():
            kept.append(clip_id)
            continue
        with Catalog.open(root) as catalog:
            if catalog.forget(record.platform, record.clip_id):
                forgotten.append(clip_id)
            else:  # pragma: no cover - the row was read a moment ago
                unknown.append(clip_id)
    return ForgetReport(tuple(forgotten), tuple(kept), tuple(unknown))
