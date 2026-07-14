from datetime import datetime, timedelta, timezone

from clipfetch.model import (
    Clip,
    ClipMetadata,
    extract_hashtags,
    optional_count,
    parse_datetime,
    timestamp_seconds,
)


def test_unicode_hashtag_extraction_preserves_order_and_deduplicates():
    caption = "#Hello, (#CAFÉ) #ქართული #hello #two_words #123 🚀#AI"
    assert extract_hashtags(caption) == (
        "hello",
        "café",
        "ქართული",
        "two_words",
        "123",
        "ai",
    )
    assert extract_hashtags("") == ()
    assert extract_hashtags(None) == ()


def test_count_normalization_distinguishes_unknown_and_real_zero():
    assert optional_count(0) == 0
    assert optional_count("15") == 15
    for invalid in (True, -1, "-1", "1.5", "١٢", 2**63):
        assert optional_count(invalid) is None


def test_timestamp_normalization_requires_seconds_and_aware_iso():
    assert timestamp_seconds(1767225600) == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert timestamp_seconds(1767225600000) is None
    assert timestamp_seconds(-1) is None
    assert parse_datetime("2026-01-01T01:00:00+01:00") == datetime(
        2026, 1, 1, tzinfo=timezone.utc
    )
    assert parse_datetime("2026-01-01T00:00:00") is None


def test_schema_v2_sidecar_is_deterministic_and_utc():
    clip = Clip(
        "instagram",
        "ABC",
        "https://cdn.invalid/expiring",
        caption="Build #Startup",
        published_at=datetime(2026, 1, 1, 1, tzinfo=timezone(timedelta(hours=1))),
    )
    value = clip.metadata()
    assert list(value) == [
        "schema_version",
        "platform",
        "id",
        "url",
        "author",
        "caption",
        "likes",
        "hashtags",
        "views",
        "comments_count",
        "shares",
        "duration_seconds",
        "published_at",
    ]
    assert value["schema_version"] == 2
    assert value["hashtags"] == ["startup"]
    assert value["published_at"] == "2026-01-01T00:00:00+00:00"
    assert "cdn" not in repr(value)


def test_legacy_sidecar_reading_derives_new_fields_without_breaking():
    metadata = ClipMetadata.from_dict(
        {
            "platform": "instagram",
            "id": "OLD",
            "author": "nasa",
            "caption": "Space #Science",
            "likes": 42,
        }
    )
    assert metadata.clip_id == "OLD"
    assert metadata.hashtags == ("science",)
    assert metadata.views is None
