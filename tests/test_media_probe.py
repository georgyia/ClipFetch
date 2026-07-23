from __future__ import annotations

from clipfetch import media_probe
from clipfetch.catalog import Catalog, MediaDetails
from clipfetch.media_probe import STATUS_OK, STATUS_UNKNOWN, parse_ffprobe, probe_file
from clipfetch.services import probe_service
from tests.webfixtures import build_fixture_library

_FFPROBE_MP4 = {
    "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": "12.5", "bit_rate": "800000"},
    "streams": [
        {"codec_type": "video", "codec_name": "h264", "width": 1080, "height": 1920},
        {"codec_type": "audio", "codec_name": "aac"},
    ],
}


def test_parse_ffprobe_extracts_details_and_compatibility():
    probe = parse_ffprobe(_FFPROBE_MP4)
    assert probe.status == STATUS_OK
    assert probe.duration_seconds == 12.5
    assert (probe.width, probe.height) == (1080, 1920)
    assert probe.video_codec == "h264"
    assert probe.audio_codec == "aac"
    assert probe.bitrate == 800000
    assert probe.container == "mov"
    assert probe.compatible is True


def test_incompatible_codec_is_flagged():
    payload = {
        "format": {"format_name": "matroska,webm"},
        "streams": [{"codec_type": "video", "codec_name": "prores"}],
    }
    assert parse_ffprobe(payload).compatible is False


def test_unknown_codecs_leave_compatibility_none():
    assert parse_ffprobe({"format": {}, "streams": []}).compatible is None


def test_probe_file_missing_is_error(tmp_path):
    result = probe_file(tmp_path / "nope.mp4")
    assert result.status == "error"


def test_probe_file_without_ffprobe_is_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(media_probe, "find_ffprobe", lambda: None)
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"not really a video")
    result = probe_file(media)
    assert result.status == STATUS_UNKNOWN


def test_migration_reaches_version_8(tmp_path):
    build_fixture_library(tmp_path / "lib")
    with Catalog.open(tmp_path / "lib") as catalog:
        assert catalog.schema_version == 8


def test_media_details_round_trip(tmp_path):
    build_fixture_library(tmp_path / "lib")
    details = MediaDetails(
        platform="instagram",
        clip_id="IG_COOK1",
        file_size=1234,
        file_mtime_ns=1,
        duration_seconds=10.0,
        width=720,
        height=1280,
        video_codec="h264",
        audio_codec="aac",
        bitrate=500000,
        container="mp4",
        compatible=True,
        status="ok",
        error=None,
        generated_at="2026-01-01T00:00:00+00:00",
    )
    with Catalog.open(tmp_path / "lib") as catalog:
        catalog.store_media_details(details)
    with Catalog.open(tmp_path / "lib") as catalog:
        loaded = catalog.get_media_details("instagram", "IG_COOK1")
    assert loaded == details


def test_probe_clip_stores_unknown_when_ffprobe_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(media_probe, "find_ffprobe", lambda: None)
    root = tmp_path / "lib"
    build_fixture_library(root)
    details = probe_service.probe_clip(root, "instagram", "IG_COOK1")
    assert details.status == STATUS_UNKNOWN
    with Catalog.open(root) as catalog:
        assert catalog.get_media_details("instagram", "IG_COOK1") is not None
