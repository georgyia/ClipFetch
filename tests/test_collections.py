import json
from datetime import date
from pathlib import Path

import pytest

from clipfetch.catalog import Catalog, CatalogRecord
from clipfetch.collections import (
    CollectionError,
    collections_path,
    delete_collection,
    export_json,
    export_m3u,
    get_collection,
    load_collections,
    resolve_collection,
    save_collection,
)
from clipfetch.library import ClipFilter
from clipfetch.topics import TopicConfig, TopicDefinition, save_topics, tag_clip


def _record(ident: str, likes: int, path: str | None = None) -> CatalogRecord:
    return CatalogRecord(
        platform="instagram",
        clip_id=ident,
        relative_path=path or f"reel_001_{ident}.mp4",
        file_size=5,
        file_mtime_ns=1,
        downloaded_at="2026-01-02T00:00:00+00:00",
        source_url="https://instagram.test/reel/" + ident,
        author="nasa",
        caption="startup advice",
        likes=likes,
        metadata_state="sidecar-v2",
        hashtags=("startup",),
        views=3_000_000,
    )


def _put(root: Path, record: CatalogRecord, *, present: bool = True) -> None:
    with Catalog.open(root) as catalog:
        catalog.upsert(record)
    if present:
        path = root / record.relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"video")


def test_every_filter_field_round_trips_exactly(tmp_path):
    save_topics(
        tmp_path,
        TopicConfig(0.5, (TopicDefinition("entrepreneurship", "startups", ("founder",)),)),
    )
    filters = ClipFilter(
        min_likes=1,
        max_likes=2,
        min_views=3,
        max_views=4,
        authors=("a", "b"),
        hashtags=("x",),
        platforms=("instagram",),
        topics=("entrepreneurship",),
        downloaded_after=date(2026, 1, 1),
        downloaded_before=date(2026, 2, 1),
    )
    save_collection(tmp_path, "viral-founders", filters)
    assert get_collection(tmp_path, "viral-founders").filters == filters
    with pytest.raises(CollectionError, match="already exists"):
        save_collection(tmp_path, "viral-founders", filters)


def test_dynamic_membership_changes_without_materialized_paths(tmp_path):
    save_collection(tmp_path, "viral", ClipFilter(min_likes=1_000_000))
    _put(tmp_path, _record("LOW", 10))
    _put(tmp_path, _record("HIGH", 2_000_000))
    assert [item.clip_id for item in resolve_collection(tmp_path, "viral").clips] == ["HIGH"]
    _put(tmp_path, _record("LOW", 3_000_000))
    assert {item.clip_id for item in resolve_collection(tmp_path, "viral").clips} == {
        "LOW",
        "HIGH",
    }
    (tmp_path / "reel_001_HIGH.mp4").unlink()
    assert [item.clip_id for item in resolve_collection(tmp_path, "viral").clips] == ["LOW"]


def test_topic_collection_and_unknown_topic_validation(tmp_path):
    save_topics(
        tmp_path,
        TopicConfig(0.5, (TopicDefinition("entrepreneurship", "startups", ("founder",)),)),
    )
    _put(tmp_path, _record("A", 2_000_000))
    tag_clip(tmp_path, "A", "entrepreneurship")
    save_collection(
        tmp_path,
        "viral-founders",
        ClipFilter(min_likes=1_000_000, topics=("entrepreneurship",)),
    )
    assert resolve_collection(tmp_path, "viral-founders").matched == 1
    with pytest.raises(CollectionError, match="unknown topic"):
        save_collection(tmp_path, "bad", ClipFilter(topics=("unknown",)))


def test_malformed_future_fields_and_name_validation(tmp_path):
    path = collections_path(tmp_path)
    path.parent.mkdir()
    path.write_text("{bad", encoding="utf-8")
    with pytest.raises(CollectionError, match="invalid collections"):
        load_collections(tmp_path)
    path.write_text(json.dumps({"schema_version": 2, "collections": []}), encoding="utf-8")
    with pytest.raises(CollectionError, match="schema"):
        load_collections(tmp_path)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "collections": [{"name": "x", "filters": {"future": True}}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(CollectionError, match="filter fields"):
        load_collections(tmp_path)
    path.unlink()
    with pytest.raises(CollectionError, match="collection names"):
        save_collection(tmp_path, "Bad Name!", ClipFilter())


def test_portable_m3u_and_stable_json_exports(tmp_path):
    save_collection(tmp_path, "all", ClipFilter())
    _put(tmp_path, _record("A", 2, "folder with spaces/ქართული ვიდეო.mp4"))
    result = resolve_collection(tmp_path, "all")
    m3u = export_m3u(result)
    assert m3u == "#EXTM3U\nfolder with spaces/ქართული ვიდეო.mp4\n"
    assert str(tmp_path) not in m3u
    value = json.loads(export_json(tmp_path, result))
    assert value["library"] == "." and value["clips"][0]["id"] == "A"
    assert value["clips"][0]["relative_path"] == "folder with spaces/ქართული ვიდეო.mp4"


def test_delete_and_unknown_collection(tmp_path):
    save_collection(tmp_path, "saved", ClipFilter())
    delete_collection(tmp_path, "saved")
    assert load_collections(tmp_path) == ()
    with pytest.raises(CollectionError, match="unknown collection"):
        resolve_collection(tmp_path, "saved")
