from __future__ import annotations

from pathlib import Path

import pytest

from clipfetch.catalog import Catalog, CatalogRecord, TopicAssignment, VisibleTextSegment
from clipfetch.semantic import semantic_document, semantic_index
from clipfetch.visible_text import (
    MAX_DECODED_FRAMES_PER_SAMPLE,
    MAX_RETAINED_CHARACTERS,
    MAX_SAMPLED_FRAMES,
    CorruptMedia,
    PyAVFrameSampler,
    RecognizedLine,
    UnsupportedMedia,
    VisibleTextResult,
    enrich_visible_text,
    retain_lines,
    sample_timestamps,
)


class FakeExtractor:
    model_id = "fake/ocr"
    revision = "v1"
    sample_policy = "fixture-policy"

    def __init__(self, interrupt_call=None):
        self.calls = []
        self.interrupt_call = interrupt_call

    def extract(self, path):
        self.calls.append(path.name)
        if self.interrupt_call == len(self.calls):
            raise KeyboardInterrupt
        if "UNSUPPORTED" in path.name:
            raise UnsupportedMedia("no video stream")
        if "CORRUPT" in path.name:
            raise CorruptMedia("invalid video")
        if "FAILED" in path.name:
            raise RuntimeError("backend failed")
        if "EMPTY" in path.name:
            return VisibleTextResult("", (), None)
        segment = VisibleTextSegment(2.0, "Build your startup", 0.97)
        return VisibleTextResult(segment.text, (segment,), segment.confidence)


class FakeEmbedder:
    model_id = "fake/embed"
    revision = "v1"

    def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


def _record(ident: str, caption: str | None = "caption") -> CatalogRecord:
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
        likes=10,
        metadata_state="catalog",
    )


def _library(root: Path, *records: CatalogRecord) -> None:
    with Catalog.open(root) as catalog:
        for record in records:
            catalog.upsert(record)
            (root / record.relative_path).write_bytes(record.clip_id.encode())


def test_sampling_policy_is_strictly_bounded():
    assert sample_timestamps(0.1) == (0.0,)
    assert sample_timestamps(5.0) == (0.0, 2.0, 4.0)
    long = sample_timestamps(10_000)
    assert len(long) == MAX_SAMPLED_FRAMES
    assert long[-1] == 58.0
    with pytest.raises(UnsupportedMedia):
        sample_timestamps(float("inf"))


def test_seek_decode_is_bounded_even_if_target_is_never_reached():
    class Frame:
        pts = 0

        def to_ndarray(self, format):
            return format

    class Stream:
        time_base = 1

    class Container:
        decoded = 0

        def seek(self, *args, **kwargs):
            pass

        def decode(self, stream):
            for _ in range(1000):
                self.decoded += 1
                yield Frame()

    container = Container()
    sampler = object.__new__(PyAVFrameSampler)
    sampled = sampler._sample_frame(container, Stream(), 500.0)

    assert sampled.image == "bgr24"
    assert container.decoded == MAX_DECODED_FRAMES_PER_SAMPLE


def test_confidence_filter_similarity_dedup_and_text_cap():
    result = retain_lines(
        [
            RecognizedLine(0.0, "  Build   your startup ", 0.91),
            RecognizedLine(2.0, "Build your startup!", 0.99),
            RecognizedLine(4.0, "incomplete mixed script", 0.81),
            RecognizedLine(6.0, "Ａ" * (MAX_RETAINED_CHARACTERS + 50), 0.95),
        ]
    )

    assert result.segments[0].timestamp_seconds == 2.0
    assert result.segments[0].text == "Build your startup!"
    assert "incomplete" not in result.text
    assert len(result.text) == MAX_RETAINED_CHARACTERS
    assert result.confidence == pytest.approx(0.97)


def test_enrichment_stores_segments_and_resumes_by_hash_model_and_policy(tmp_path):
    _library(tmp_path, _record("A"))
    extractor = FakeExtractor()

    first = enrich_visible_text(tmp_path, extractor)
    assert first.completed == 1
    with Catalog.open(tmp_path) as catalog:
        record = catalog.get("instagram", "A")
        assert record.visible_text == "Build your startup"
        assert record.visible_text_segments[0].timestamp_seconds == 2.0
        assert record.visible_text_confidence == pytest.approx(0.97)
        assert record.visible_text_source_hash
        assert record.visible_text_sample_policy == "fixture-policy"
    assert enrich_visible_text(tmp_path, extractor).skipped == 1
    assert len(extractor.calls) == 1

    (tmp_path / "reel_001_A.mp4").write_bytes(b"changed")
    assert enrich_visible_text(tmp_path, extractor).completed == 1
    extractor.revision = "v2"
    assert enrich_visible_text(tmp_path, extractor).completed == 1


def test_terminal_and_retryable_outcomes_are_independent(tmp_path):
    _library(
        tmp_path,
        _record("EMPTY"),
        _record("UNSUPPORTED"),
        _record("CORRUPT"),
        _record("FAILED"),
        _record("GOOD"),
    )
    first = enrich_visible_text(tmp_path, FakeExtractor())
    assert (
        first.completed,
        first.empty,
        first.unsupported,
        first.corrupt,
        first.failed,
    ) == (1, 1, 1, 1, 1)
    second = enrich_visible_text(tmp_path, FakeExtractor())
    assert second.skipped == 4 and second.failed == 1


def test_incremental_commit_survives_interruption(tmp_path):
    _library(tmp_path, _record("A"), _record("Z"))
    with pytest.raises(KeyboardInterrupt):
        enrich_visible_text(tmp_path, FakeExtractor(interrupt_call=2))
    with Catalog.open(tmp_path) as catalog:
        assert catalog.get("instagram", "A").visible_text_status == "complete"
        assert catalog.get("instagram", "Z").visible_text_status is None

    resumed = enrich_visible_text(tmp_path, FakeExtractor())
    assert resumed.skipped == 1 and resumed.completed == 1


def test_visible_text_drives_semantics_and_preserves_manual_topics(tmp_path):
    _library(tmp_path, _record("A", caption="founder story"))
    assert semantic_index(tmp_path, FakeEmbedder()).indexed == 1
    with Catalog.open(tmp_path) as catalog:
        catalog.set_manual_topic("instagram", "A", "entrepreneurship")
        catalog.replace_model_topics(
            "instagram",
            "A",
            [
                TopicAssignment(
                    "instagram",
                    "A",
                    "generated",
                    0.9,
                    "model",
                    "fake/topics",
                    "v1",
                    "definition",
                    "input",
                    0.5,
                    "2026-01-01T00:00:00+00:00",
                )
            ],
        )

    enrich_visible_text(tmp_path, FakeExtractor())

    with Catalog.open(tmp_path) as catalog:
        record = catalog.get("instagram", "A")
        assert semantic_document(record) == (
            "caption: founder story\nvisible text: Build your startup"
        )
        assert catalog.get_embedding("instagram", "A", "fake/embed", "v1") is None
        assert catalog.topic_names("instagram", "A") == ("entrepreneurship",)
