from __future__ import annotations

from clipfetch.catalog import Catalog, MediaDetails
from clipfetch.services import quality_service
from clipfetch.services.quality_service import (
    TIER_FULL_HD,
    TIER_HD,
    TIER_SD,
    TIER_UHD,
    TIER_UNKNOWN,
    tier_for,
)
from tests.webfixtures import build_fixture_library


def _details(height, *, status="ok", width=None):
    return MediaDetails(
        platform="instagram",
        clip_id="IG_COOK1",
        file_size=1,
        file_mtime_ns=1,
        duration_seconds=10.0,
        width=width,
        height=height,
        video_codec="h264",
        audio_codec="aac",
        bitrate=1,
        container="mp4",
        compatible=True,
        status=status,
        error=None,
        generated_at="2026-01-01T00:00:00+00:00",
    )


def test_tiers_by_resolution():
    assert tier_for(_details(480)).slug == TIER_SD
    assert tier_for(_details(720)).slug == TIER_HD
    assert tier_for(_details(1080)).slug == TIER_FULL_HD
    assert tier_for(_details(2160)).slug == TIER_UHD


def test_unprobed_or_unknown_is_unknown():
    assert tier_for(None).slug == TIER_UNKNOWN
    assert tier_for(_details(None)).slug == TIER_UNKNOWN
    assert tier_for(_details(1080, status="unknown")).slug == TIER_UNKNOWN


def test_tier_is_explainable():
    tier = tier_for(_details(1920, width=1080))
    assert tier.label == "Full HD"
    assert "1080x1920" in tier.reason


def test_media_view_reports_unprobed():
    view = quality_service.media_view(None)
    assert view["status"] == "unprobed"
    assert view["tier"]["slug"] == TIER_UNKNOWN


def test_high_quality_ids_selects_full_hd_and_above(tmp_path):
    root = tmp_path / "lib"
    build_fixture_library(root)
    with Catalog.open(root) as catalog:
        catalog.store_media_details(_details(1920, width=1080))  # IG_COOK1 -> Full HD
        low = _details(480)
        catalog.store_media_details(
            MediaDetails(**{**low.__dict__, "clip_id": "IG_TECH1"})  # SD -> excluded
        )
    ids = quality_service.high_quality_ids(root)
    assert "IG_COOK1" in ids
    assert "IG_TECH1" not in ids
