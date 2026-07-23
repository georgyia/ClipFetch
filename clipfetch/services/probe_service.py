"""Probe a catalogued clip's media and persist the technical details.

Bridges :mod:`clipfetch.media_probe` and the catalog's ``media_details`` table. Probing is gradual
and idempotent: it can be run for any clip at any time, degrades to an ``unknown`` row when
``ffprobe`` is unavailable, and never raises for a missing or unreadable file.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from clipfetch import media_probe
from clipfetch.catalog import Catalog, CatalogError, MediaDetails


def probe_clip(
    root: Path, platform: str, clip_id: str, *, ffprobe: str | None = None
) -> MediaDetails:
    """Probe one clip's media file and store the result, returning the stored details."""
    with Catalog.open(root) as catalog:
        record = catalog.get(platform, clip_id)
        if record is None:
            raise CatalogError(f"unknown clip: {platform}/{clip_id}")
        media_path = root / record.relative_path
        probe = media_probe.probe_file(media_path, ffprobe=ffprobe)
        try:
            stat = os.stat(media_path)
            file_size, file_mtime_ns = stat.st_size, stat.st_mtime_ns
        except OSError:
            file_size, file_mtime_ns = record.file_size, record.file_mtime_ns
        details = MediaDetails(
            platform=platform,
            clip_id=clip_id,
            file_size=file_size,
            file_mtime_ns=file_mtime_ns,
            duration_seconds=probe.duration_seconds,
            width=probe.width,
            height=probe.height,
            video_codec=probe.video_codec,
            audio_codec=probe.audio_codec,
            bitrate=probe.bitrate,
            container=probe.container,
            compatible=probe.compatible,
            status=probe.status,
            error=probe.error,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        catalog.store_media_details(details)
        return details
