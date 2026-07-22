from __future__ import annotations

import json

from clipfetch.catalog import CatalogRecord
from clipfetch.contracts import (
    CONTRACT_SCHEMA_VERSION,
    ApiError,
    ClipPage,
    clip_detail,
    clip_summary,
)

_SUMMARY_KEYS = {
    "id",
    "platform",
    "author",
    "caption",
    "likes",
    "views",
    "comments_count",
    "duration_seconds",
    "published_at",
    "downloaded_at",
    "available",
    "metadata_state",
    "hashtags",
    "topics",
    "source_url",
}

# Fields that must never cross the API boundary in a clip contract.
_FORBIDDEN_KEYS = {
    "relative_path",
    "file_mtime_ns",
    "clip_id",
    "transcript_text",
    "comment_text",
    "transcript_error",
    "comment_error",
}


def _record(**overrides) -> CatalogRecord:
    base = dict(
        platform="instagram",
        clip_id="ABC123",
        relative_path="instagram/ABC123.mp4",
        file_size=4096,
        file_mtime_ns=1_700_000_000_000_000_000,
        downloaded_at="2026-06-01T09:00:00+00:00",
        source_url="https://example.invalid/p/ABC123",
        author="creator",
        caption="hello #world",
        likes=1000,
        metadata_state="sidecar-v2",
        hashtags=("world",),
        views=5000,
        comments_count=12,
    )
    base.update(overrides)
    return CatalogRecord(**base)


def test_summary_has_exact_stable_keys_and_maps_id():
    value = clip_summary(_record(), topics=("technology",)).to_dict()
    assert set(value) == _SUMMARY_KEYS
    assert value["id"] == "ABC123"
    assert value["hashtags"] == ["world"]
    assert value["topics"] == ["technology"]
    assert isinstance(value["hashtags"], list) and isinstance(value["topics"], list)


def test_detail_extends_summary_and_reports_enrichment():
    record = _record(
        shares=7,
        transcript_text="a transcript body",
        transcript_status="completed",
        transcript_language="en",
        comment_text="a comment body",
        comment_status="completed",
    )
    value = clip_detail(record).to_dict()
    assert _SUMMARY_KEYS <= set(value)
    assert value["schema_version"] == CONTRACT_SCHEMA_VERSION
    assert value["shares"] == 7
    assert value["file_size_bytes"] == 4096
    assert value["has_transcript"] is True and value["transcript_language"] == "en"
    assert value["has_comments"] is True and value["comment_status"] == "completed"


def test_detail_reports_absent_enrichment_as_false():
    value = clip_detail(_record()).to_dict()
    assert value["has_transcript"] is False
    assert value["transcript_status"] is None
    assert value["has_comments"] is False


def test_no_device_or_transport_fields_leak():
    record = _record(transcript_text="secret transcript", comment_text="secret comment")
    serialized = json.dumps(clip_detail(record).to_dict())
    for forbidden in _FORBIDDEN_KEYS:
        assert forbidden not in serialized
    # The on-disk path and transcript/comment bodies must not appear as values either.
    assert "instagram/ABC123.mp4" not in serialized
    assert "secret transcript" not in serialized
    assert "secret comment" not in serialized


def test_clip_page_envelope_is_stable():
    page = ClipPage(items=(clip_summary(_record()),), next_cursor="opaque-cursor", total_matched=42)
    value = page.to_dict()
    assert list(value) == ["schema_version", "items", "next_cursor", "total_matched"]
    assert value["next_cursor"] == "opaque-cursor"
    assert value["total_matched"] == 42
    assert len(value["items"]) == 1 and value["items"][0]["id"] == "ABC123"


def test_error_envelope_shape():
    value = ApiError(
        code="media_unavailable",
        message="The local media file could not be found.",
        request_id="req_01",
        recovery_actions=("locate_file", "retry_download"),
    ).to_dict()
    assert set(value) == {"error"}
    error = value["error"]
    assert error["code"] == "media_unavailable"
    assert error["request_id"] == "req_01"
    assert error["details"]["recovery_actions"] == ["locate_file", "retry_download"]
