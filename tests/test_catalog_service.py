from __future__ import annotations

from pathlib import Path

import pytest

from clipfetch.catalog import Catalog, CatalogError, CatalogRecord
from clipfetch.library import ClipFilter
from clipfetch.services.catalog_service import (
    InvalidCursorError,
    get_clip,
    list_clips,
)


def _record(ident: str, *, likes: int | None = None, available: bool = True) -> CatalogRecord:
    # Ascending ident suffix drives a stable, predictable date order.
    return CatalogRecord(
        platform="instagram",
        clip_id=ident,
        relative_path=f"instagram/{ident}.mp4",
        file_size=10,
        file_mtime_ns=20,
        downloaded_at=f"2026-06-{int(ident[-2:]):02d}T00:00:00+00:00",
        source_url=f"https://example.invalid/{ident}",
        author="creator",
        caption=None,
        likes=likes,
        metadata_state="sidecar-v2",
        available=available,
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


def _five(tmp_path: Path) -> Path:
    return _library(
        tmp_path,
        _record("CLIP01", likes=100),
        _record("CLIP02", likes=200),
        _record("CLIP03", likes=300),
        _record("CLIP04", likes=400),
        _record("CLIP05", likes=500),
    )


def test_pagination_walks_every_clip_once(tmp_path):
    _five(tmp_path)

    page1 = list_clips(tmp_path, limit=2)
    assert page1.total_matched == 5
    assert len(page1.items) == 2
    assert page1.next_cursor is not None

    page2 = list_clips(tmp_path, limit=2, cursor=page1.next_cursor)
    page3 = list_clips(tmp_path, limit=2, cursor=page2.next_cursor)
    assert len(page3.items) == 1
    assert page3.next_cursor is None

    seen = [item.id for page in (page1, page2, page3) for item in page.items]
    assert sorted(seen) == ["CLIP01", "CLIP02", "CLIP03", "CLIP04", "CLIP05"]
    assert len(seen) == len(set(seen))


def test_default_sort_is_newest_first(tmp_path):
    _five(tmp_path)
    page = list_clips(tmp_path, limit=5)
    assert [item.id for item in page.items] == ["CLIP05", "CLIP04", "CLIP03", "CLIP02", "CLIP01"]


def test_filters_are_applied(tmp_path):
    _five(tmp_path)
    page = list_clips(tmp_path, ClipFilter(min_likes=300), sort="likes")
    assert [item.id for item in page.items] == ["CLIP05", "CLIP04", "CLIP03"]
    assert page.total_matched == 3


def test_limit_is_clamped(tmp_path):
    _five(tmp_path)
    page = list_clips(tmp_path, limit=10_000)
    assert len(page.items) == 5
    assert page.next_cursor is None


def test_topics_are_attached_to_summaries(tmp_path):
    _library(tmp_path, _record("CLIP01", likes=100))
    with Catalog.open(tmp_path) as catalog:
        catalog.set_manual_topic("instagram", "CLIP01", "technology")

    page = list_clips(tmp_path)
    assert page.items[0].topics == ("technology",)


def test_get_clip_returns_detail_and_missing_raises(tmp_path):
    _library(tmp_path, _record("CLIP01", likes=100))

    detail = get_clip(tmp_path, "CLIP01")
    assert detail.summary.id == "CLIP01"
    assert detail.file_size_bytes == 10
    assert detail.has_transcript is False

    with pytest.raises(CatalogError, match="not found"):
        get_clip(tmp_path, "NOPE")


def test_invalid_cursor_is_rejected(tmp_path):
    _five(tmp_path)
    with pytest.raises(InvalidCursorError):
        list_clips(tmp_path, cursor="not-a-cursor!!")
