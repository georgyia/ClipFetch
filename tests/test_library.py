from datetime import date
from pathlib import Path

import pytest

from clipfetch.catalog import Catalog, CatalogRecord
from clipfetch.library import (
    ClipFilter,
    find_clip,
    parse_date,
    parse_magnitude,
    query_library,
    query_to_dict,
)


def _record(
    ident: str,
    *,
    likes: int | None = None,
    views: int | None = None,
    author: str | None = None,
    hashtags: tuple[str, ...] = (),
    downloaded_at: str = "2026-01-01T00:00:00+00:00",
    available: bool = True,
) -> CatalogRecord:
    return CatalogRecord(
        platform="instagram",
        clip_id=ident,
        relative_path=f"reel_001_{ident}.mp4",
        file_size=10,
        file_mtime_ns=20,
        downloaded_at=downloaded_at,
        source_url=None,
        author=author,
        caption=None,
        likes=likes,
        metadata_state="sidecar-v2",
        available=available,
        hashtags=hashtags,
        views=views,
    )


def _library(tmp_path: Path, *records: CatalogRecord) -> Path:
    with Catalog.open(tmp_path) as catalog:
        for record in records:
            catalog.upsert(record)
            if record.available:
                path = tmp_path / record.relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"video")
    return tmp_path


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0", 0),
        (" 999999 ", 999_999),
        ("1m", 1_000_000),
        ("1.5M", 1_500_000),
        ("2k", 2_000),
        ("3B", 3_000_000_000),
    ],
)
def test_parse_magnitude(text, expected):
    assert parse_magnitude(text) == expected


@pytest.mark.parametrize("text", ["", "-1", "1x", "1.2", "NaN", "1e30", "9223372037b"])
def test_parse_magnitude_rejects_invalid_negative_fractional_and_overflow(text):
    with pytest.raises(ValueError):
        parse_magnitude(text)


def test_exact_boundaries_and_unknown_values(tmp_path):
    _library(
        tmp_path,
        _record("LOW", likes=999_999),
        _record("BOUNDARY", likes=1_000_000),
        _record("UNKNOWN", likes=None),
        _record("ZERO", likes=0),
    )
    result = query_library(tmp_path, ClipFilter(min_likes=1_000_000), sort="likes")
    assert [record.clip_id for record in result.clips] == ["BOUNDARY"]
    assert result.matched == 1
    assert result.excluded == 3
    assert result.unknown_required_metadata == 1


def test_same_dimension_or_cross_dimension_and(tmp_path):
    _library(
        tmp_path,
        _record("A", likes=2_000_000, author="nasa", hashtags=("space",)),
        _record("B", likes=3_000_000, author="spacex", hashtags=("entrepreneurship",)),
        _record("C", likes=4_000_000, author="other", hashtags=("entrepreneurship",)),
    )
    filters = ClipFilter(
        min_likes=1_000_000,
        authors=("NASA", "spacex", "nasa"),
        hashtags=("entrepreneurship",),
    )
    result = query_library(tmp_path, filters)
    assert [record.clip_id for record in result.clips] == ["B"]


def test_dates_are_inclusive_and_sort_limit_offset_are_stable(tmp_path):
    _library(
        tmp_path,
        _record("A", likes=10, downloaded_at="2026-01-01T23:00:00+00:00"),
        _record("B", likes=10, downloaded_at="2026-01-02T00:00:00+00:00"),
        _record("C", likes=5, downloaded_at="2026-01-03T00:00:00+00:00"),
    )
    filters = ClipFilter(
        downloaded_after=date(2026, 1, 1), downloaded_before=date(2026, 1, 2)
    )
    result = query_library(tmp_path, filters, sort="likes", offset=1, limit=1)
    assert result.matched == 2
    assert [record.clip_id for record in result.clips] == ["B"]
    assert parse_date(" 2026-01-02 ") == date(2026, 1, 2)
    with pytest.raises(ValueError):
        parse_date("02/01/2026")


def test_missing_files_are_excluded_and_json_schema_is_stable(tmp_path):
    _library(tmp_path, _record("HERE", available=True), _record("GONE", available=False))
    result = query_library(tmp_path)
    value = query_to_dict(result)
    assert list(value) == [
        "schema_version",
        "matched",
        "excluded",
        "unknown_required_metadata",
        "clips",
    ]
    assert value["matched"] == 1 and value["excluded"] == 1
    assert value["clips"][0]["id"] == "HERE"


def test_find_clip_reports_missing_and_returns_full_record(tmp_path):
    _library(tmp_path, _record("ABC", likes=42))
    assert find_clip(tmp_path, "ABC").likes == 42
    with pytest.raises(Exception, match="not found"):
        find_clip(tmp_path, "NOPE")
