"""Technical quality tiers derived from probed media.

A *tier* summarizes how good the actual downloaded file is — measured from the probed
:class:`~clipfetch.catalog.MediaDetails` (resolution first), and deliberately distinct from the
download-time :class:`~clipfetch.model.Quality` preference, which is a request, not a measurement.
Tiers are explainable: each carries a human label and the reason it was assigned, so a badge or
filter can say *why*.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clipfetch.catalog import Catalog, MediaDetails

TIER_UNKNOWN = "unknown"
TIER_SD = "sd"
TIER_HD = "hd"
TIER_FULL_HD = "full_hd"
TIER_UHD = "uhd"

_LABELS = {
    TIER_UNKNOWN: "Unknown",
    TIER_SD: "SD",
    TIER_HD: "HD",
    TIER_FULL_HD: "Full HD",
    TIER_UHD: "4K",
}

#: A clip is a "high-quality pick" at Full HD or above.
HIGH_QUALITY_TIERS = frozenset({TIER_FULL_HD, TIER_UHD})
_HIGH_QUALITY_MIN_HEIGHT = 1080


@dataclass(frozen=True)
class QualityTier:
    slug: str
    label: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"slug": self.slug, "label": self.label, "reason": self.reason}


def _tier_slug(height: int | None) -> str:
    if height is None or height <= 0:
        return TIER_UNKNOWN
    if height < 720:
        return TIER_SD
    if height < 1080:
        return TIER_HD
    if height < 2160:
        return TIER_FULL_HD
    return TIER_UHD


def tier_for(details: MediaDetails | None) -> QualityTier:
    """Classify probed media into an explainable tier. Unprobed/unknown media is ``unknown``."""
    if details is None or details.status != "ok" or details.height is None:
        return QualityTier(TIER_UNKNOWN, _LABELS[TIER_UNKNOWN], "not probed yet")
    slug = _tier_slug(details.height)
    resolution = f"{details.width or '?'}x{details.height}"
    return QualityTier(slug, _LABELS[slug], f"{resolution} source")


def media_view(details: MediaDetails | None) -> dict[str, Any]:
    """The probed technical block surfaced on the clip detail contract (never any device path)."""
    tier = tier_for(details)
    block: dict[str, Any] = {"tier": tier.to_dict(), "status": "unprobed"}
    if details is not None:
        block.update(
            {
                "status": details.status,
                "width": details.width,
                "height": details.height,
                "duration_seconds": details.duration_seconds,
                "video_codec": details.video_codec,
                "audio_codec": details.audio_codec,
                "bitrate": details.bitrate,
                "container": details.container,
                "compatible": details.compatible,
            }
        )
    return block


def high_quality_ids(root: Path, *, limit: int = 48) -> tuple[str, ...]:
    """Clip ids whose probed height is Full HD or above, newest first — for High-Quality Picks."""
    with Catalog.open(root) as catalog:
        return tuple(catalog.clip_ids_by_min_height(_HIGH_QUALITY_MIN_HEIGHT, limit=limit))
