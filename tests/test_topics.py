import json
from pathlib import Path

import pytest

from clipfetch.catalog import Catalog, CatalogRecord
from clipfetch.library import ClipFilter, query_library
from clipfetch.topics import (
    TopicConfig,
    TopicDefinition,
    TopicError,
    add_topic,
    assignment_details,
    categorize_library,
    init_topics,
    load_topics,
    remove_topic,
    save_topics,
    tag_clip,
    topics_path,
)


class FakeEmbedder:
    model_id = "test/topics"
    revision = "v1"

    def __init__(self):
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))
        result = []
        for text in texts:
            value = text.casefold()
            if "entertainment" in value or "movie" in value:
                result.append([0.0, 1.0, 0.0])
            elif "business" in value:
                result.append([0.9, 0.1, 0.0])
            elif "technology" in value:
                result.append([0.8, 0.0, 0.2])
            elif "startup" in value or "entrepreneur" in value:
                result.append([1.0, 0.0, 0.0])
            else:
                result.append([0.0, 0.0, 1.0])
        return result


def _record(ident: str, caption: str) -> CatalogRecord:
    return CatalogRecord(
        platform="instagram",
        clip_id=ident,
        relative_path=f"reel_001_{ident}.mp4",
        file_size=5,
        file_mtime_ns=1,
        downloaded_at="2026-01-01T00:00:00+00:00",
        source_url=None,
        author="author",
        caption=caption,
        likes=2_000_000,
        metadata_state="sidecar-v2",
    )


def _library(root: Path, *records: CatalogRecord) -> None:
    with Catalog.open(root) as catalog:
        for record in records:
            catalog.upsert(record)
            (root / record.relative_path).write_bytes(b"video")


def _config(root: Path, threshold: float = 0.75) -> None:
    save_topics(
        root,
        TopicConfig(
            threshold,
            (
                TopicDefinition("entrepreneurship", "startup founders", ("startup",)),
                TopicDefinition("business", "business operations", ("company",)),
                TopicDefinition("technology", "technology products", ("software",)),
                TopicDefinition("entertainment", "movies and comedy", ("movie",)),
            ),
        ),
    )


def test_init_add_list_remove_and_duplicate_validation(tmp_path):
    config = init_topics(tmp_path)
    assert len(config.topics) == 11
    assert topics_path(tmp_path).exists()
    added = add_topic(tmp_path, "climate-tech", "climate technology", ["clean energy"])
    assert added.name == "climate-tech"
    with pytest.raises(TopicError, match="already exists"):
        add_topic(tmp_path, "climate-tech", "duplicate", ["x"])
    with pytest.raises(TopicError, match="topic names"):
        add_topic(tmp_path, "Bad Name!", "bad", ["x"])
    remove_topic(tmp_path, "climate-tech")
    assert "climate-tech" not in {topic.name for topic in load_topics(tmp_path).topics}


def test_invalid_future_and_legacy_topics_json(tmp_path):
    path = topics_path(tmp_path)
    path.parent.mkdir()
    path.write_text("{bad", encoding="utf-8")
    with pytest.raises(TopicError, match="invalid topics file"):
        load_topics(tmp_path)
    path.write_text(json.dumps({"schema_version": 99, "topics": []}), encoding="utf-8")
    with pytest.raises(TopicError, match="unsupported"):
        load_topics(tmp_path)
    path.write_text(
        json.dumps(
            {
                "topics": [
                    {"name": "legacy", "description": "old schema", "examples": ["old"]}
                ]
            }
        ),
        encoding="utf-8",
    )
    assert load_topics(tmp_path).topics[0].name == "legacy"


def test_multilabel_top_three_threshold_and_uncategorized(tmp_path):
    _config(tmp_path)
    _library(
        tmp_path,
        _record("STARTUP", "startup business technology advice"),
        _record("MOVIE", "movie entertainment"),
        _record("OTHER", "gardening flowers"),
    )
    report = categorize_library(tmp_path, FakeEmbedder())
    assert report.categorized == 3 and report.uncategorized == 1
    with Catalog.open(tmp_path) as catalog:
        startup = catalog.topic_names("instagram", "STARTUP")
        assert startup == ("business", "entrepreneurship", "technology")
        other = catalog.topic_assignments("instagram", "OTHER")
        assert other[0].topic == "uncategorized"


def test_manual_override_survives_reindex_and_can_be_removed(tmp_path):
    _config(tmp_path)
    _library(tmp_path, _record("A", "movie entertainment"))
    tag_clip(tmp_path, "A", "entrepreneurship")
    categorize_library(tmp_path, FakeEmbedder())
    with Catalog.open(tmp_path) as catalog:
        assignments = catalog.topic_assignments("instagram", "A")
        assert any(item.topic == "entrepreneurship" and item.provenance == "manual"
                   for item in assignments)
    categorize_library(tmp_path, FakeEmbedder())
    tag_clip(tmp_path, "A", "entrepreneurship", remove=True)
    with Catalog.open(tmp_path) as catalog:
        assert not any(item.provenance == "manual" for item in
                       catalog.topic_assignments("instagram", "A"))


def test_selective_clip_invalidation_and_topic_filter(tmp_path):
    _config(tmp_path)
    _library(tmp_path, _record("A", "startup advice"), _record("B", "movie review"))
    first = categorize_library(tmp_path, FakeEmbedder())
    assert first.categorized == 2
    second = categorize_library(tmp_path, FakeEmbedder())
    assert second.categorized == 0 and second.unchanged == 2
    with Catalog.open(tmp_path) as catalog:
        catalog.upsert(_record("A", "updated startup advice"))
    third = categorize_library(tmp_path, FakeEmbedder())
    assert third.categorized == 1 and third.unchanged == 1
    result = query_library(tmp_path, ClipFilter(topics=("entrepreneurship",)))
    assert [record.clip_id for record in result.clips] == ["A"]
    details = assignment_details(tmp_path, "instagram", "A")
    assert details[0]["description"] and details[0]["provenance"] == "model"
