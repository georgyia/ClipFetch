from __future__ import annotations

from pathlib import Path

import pytest

from clipfetch.catalog import Catalog, CatalogRecord
from clipfetch.collections import CollectionError
from clipfetch.library import ClipFilter
from clipfetch.services import collection_service, topic_service
from clipfetch.topics import TopicError, init_topics


def _record(ident: str, *, likes: int) -> CatalogRecord:
    return CatalogRecord(
        platform="instagram",
        clip_id=ident,
        relative_path=f"instagram/{ident}.mp4",
        file_size=10,
        file_mtime_ns=20,
        downloaded_at=f"2026-06-{int(ident[-2:]):02d}T00:00:00+00:00",
        source_url=None,
        author="creator",
        caption=None,
        likes=likes,
        metadata_state="sidecar-v2",
    )


def _library(tmp_path: Path) -> Path:
    records = {
        "CLIP01": (100, "technology"),
        "CLIP02": (2_000_000, "technology"),
        "CLIP03": (500, None),
        "CLIP04": (3_000_000, "food"),
    }
    with Catalog.open(tmp_path) as catalog:
        for ident, (likes, _topic) in records.items():
            catalog.upsert(_record(ident, likes=likes))
            path = tmp_path / f"instagram/{ident}.mp4"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"video")
    init_topics(tmp_path)
    with Catalog.open(tmp_path) as catalog:
        for ident, (_likes, topic) in records.items():
            if topic:
                catalog.set_manual_topic("instagram", ident, topic)
    return tmp_path


# --- topics -------------------------------------------------------------------


def test_list_topics_reports_counts(tmp_path):
    _library(tmp_path)
    counts = {topic.slug: topic.clip_count for topic in topic_service.list_topics(tmp_path)}
    assert counts["technology"] == 2
    assert counts["food"] == 1
    assert counts["travel"] == 0


def test_get_topic_and_unknown(tmp_path):
    _library(tmp_path)
    assert topic_service.get_topic(tmp_path, "technology").clip_count == 2
    assert topic_service.get_topic(tmp_path, "technology").to_dict() == {
        "slug": "technology",
        "description": "software, hardware, science and digital products",
        "clip_count": 2,
    }
    with pytest.raises(TopicError, match="unknown topic"):
        topic_service.get_topic(tmp_path, "nope")


def test_list_topic_clips_paginates_and_validates(tmp_path):
    _library(tmp_path)
    page = topic_service.list_topic_clips(tmp_path, "technology")
    assert {item.id for item in page.items} == {"CLIP01", "CLIP02"}
    assert page.total_matched == 2
    with pytest.raises(TopicError, match="unknown topic"):
        topic_service.list_topic_clips(tmp_path, "nope")


# --- collections --------------------------------------------------------------


def test_create_list_and_resolve_collection(tmp_path):
    _library(tmp_path)
    summary = collection_service.create_collection(
        tmp_path, "popular", ClipFilter(min_likes=1_000_000)
    )
    assert summary.id == "popular"
    assert summary.clip_count == 2
    assert summary.filters["min_likes"] == 1_000_000

    listed = {item.id for item in collection_service.list_collections(tmp_path)}
    assert listed == {"popular"}

    page = collection_service.list_collection_clips(tmp_path, "popular", sort="likes")
    assert [item.id for item in page.items] == ["CLIP04", "CLIP02"]


def test_delete_collection_and_unknown(tmp_path):
    _library(tmp_path)
    collection_service.create_collection(tmp_path, "popular", ClipFilter(min_likes=1_000_000))
    collection_service.delete_collection(tmp_path, "popular")
    assert collection_service.list_collections(tmp_path) == ()
    with pytest.raises(CollectionError):
        collection_service.get_collection_summary(tmp_path, "popular")


def test_create_collection_rejects_unknown_topic(tmp_path):
    _library(tmp_path)
    with pytest.raises(CollectionError, match="unknown topic"):
        collection_service.create_collection(
            tmp_path, "bad", ClipFilter(topics=("not-a-real-topic",))
        )
