import sys
from pathlib import Path

import pytest

from clipfetch.catalog import Catalog, CatalogRecord, TopicAssignment
from clipfetch.library import ClipFilter
from clipfetch.semantic import semantic_document, semantic_index
from clipfetch.topics import (
    TopicConfig,
    TopicDefinition,
    categorize_library,
    save_topics,
    tag_clip,
)
from clipfetch.transcription import (
    FasterWhisperTranscriber,
    TranscriptionError,
    TranscriptResult,
    UnsupportedMedia,
    enrich_transcripts,
    normalize_transcript,
)


class FakeTranscriber:
    model_id = "fake/base"
    revision = "v1"

    def __init__(self, interrupt_call=None):
        self.calls = []
        self.interrupt_call = interrupt_call

    def transcribe(self, path):
        self.calls.append(path.name)
        if self.interrupt_call == len(self.calls):
            raise KeyboardInterrupt
        if "UNSUPPORTED" in path.name:
            raise UnsupportedMedia("no audio stream")
        if "BAD" in path.name:
            raise RuntimeError("decode failed")
        if "SILENT" in path.name:
            return TranscriptResult("   ", None)
        return TranscriptResult("  hello\n  multilingual   world ", "en")


class FakeEmbedder:
    model_id = "fake/embed"
    revision = "v1"

    def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


def _record(ident: str, *, likes: int = 10, caption: str | None = None) -> CatalogRecord:
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
        likes=likes,
        metadata_state="catalog",
    )


def _library(root: Path, *records: CatalogRecord) -> None:
    with Catalog.open(root) as catalog:
        for record in records:
            catalog.upsert(record)
            (root / record.relative_path).write_bytes(record.clip_id.encode())


def test_success_whitespace_language_and_hash_resume(tmp_path):
    _library(tmp_path, _record("A"))
    transcriber = FakeTranscriber()
    report = enrich_transcripts(tmp_path, transcriber)
    assert report.completed == 1
    with Catalog.open(tmp_path) as catalog:
        record = catalog.get("instagram", "A")
        assert record.transcript_text == "hello multilingual world"
        assert record.transcript_language == "en"
        assert record.transcript_status == "complete"
        assert record.transcript_source_hash
    second = enrich_transcripts(tmp_path, transcriber)
    assert second.skipped == 1 and len(transcriber.calls) == 1
    (tmp_path / "reel_001_A.mp4").write_bytes(b"changed")
    third = enrich_transcripts(tmp_path, transcriber)
    assert third.completed == 1 and len(transcriber.calls) == 2


def test_model_change_force_and_metadata_filter(tmp_path):
    _library(tmp_path, _record("LOW", likes=1), _record("HIGH", likes=100))
    first = FakeTranscriber()
    report = enrich_transcripts(tmp_path, first, ClipFilter(min_likes=50))
    assert report.selected == 1 and first.calls == ["reel_001_HIGH.mp4"]
    changed_model = FakeTranscriber()
    changed_model.revision = "v2"
    assert enrich_transcripts(tmp_path, changed_model, ClipFilter(min_likes=50)).completed == 1
    assert (
        enrich_transcripts(tmp_path, changed_model, ClipFilter(min_likes=50), force=True).completed
        == 1
    )


def test_uncategorized_topic_filter(tmp_path):
    _library(tmp_path, _record("OTHER"), _record("MATCH"))
    with Catalog.open(tmp_path) as catalog:
        catalog.replace_model_topics(
            "instagram",
            "MATCH",
            [
                TopicAssignment(
                    platform="instagram",
                    clip_id="MATCH",
                    topic="uncategorized",
                    confidence=0.0,
                    provenance="model",
                    model_id="fake/topics",
                    model_revision="v1",
                    definition_hash="hash",
                    input_hash="input",
                    threshold=0.5,
                    generated_at="2026-01-01T00:00:00+00:00",
                )
            ],
        )
    transcriber = FakeTranscriber()
    report = enrich_transcripts(tmp_path, transcriber, ClipFilter(topics=("uncategorized",)))
    assert report.selected == 1
    assert transcriber.calls == ["reel_001_MATCH.mp4"]


def test_silent_unsupported_and_corrupt_are_independent(tmp_path):
    _library(
        tmp_path,
        _record("SILENT"),
        _record("UNSUPPORTED"),
        _record("BAD"),
        _record("GOOD"),
    )
    report = enrich_transcripts(tmp_path, FakeTranscriber())
    assert (report.completed, report.silent, report.unsupported, report.failed) == (1, 1, 1, 1)
    with Catalog.open(tmp_path) as catalog:
        assert catalog.get("instagram", "SILENT").transcript_status == "silent"
        assert catalog.get("instagram", "UNSUPPORTED").transcript_status == "unsupported"
        assert catalog.get("instagram", "BAD").transcript_status == "failed"


def test_incremental_commit_survives_clean_interruption(tmp_path):
    _library(tmp_path, _record("A_SECOND"), _record("Z_FIRST"))
    with pytest.raises(KeyboardInterrupt):
        enrich_transcripts(tmp_path, FakeTranscriber(interrupt_call=2))
    with Catalog.open(tmp_path) as catalog:
        assert catalog.get("instagram", "A_SECOND").transcript_status == "complete"
        assert catalog.get("instagram", "Z_FIRST").transcript_status is None
    resumed = enrich_transcripts(tmp_path, FakeTranscriber())
    assert resumed.skipped == 1 and resumed.completed == 1


def test_transcript_drives_semantics_and_preserves_manual_topic(tmp_path):
    _library(
        tmp_path,
        _record("A", caption="startup story"),
        _record("B", caption="neighboring clip"),
    )
    save_topics(
        tmp_path,
        TopicConfig(
            0.5,
            (
                TopicDefinition("entrepreneurship", "startups", ("founder",)),
                TopicDefinition("learning", "education", ("study",)),
            ),
        ),
    )
    tag_clip(tmp_path, "A", "entrepreneurship")
    assert semantic_index(tmp_path, FakeEmbedder()).indexed == 2
    with Catalog.open(tmp_path) as catalog:
        for ident in ("A", "B"):
            catalog.replace_model_topics(
                "instagram",
                ident,
                [
                    TopicAssignment(
                        platform="instagram",
                        clip_id=ident,
                        topic="uncategorized",
                        confidence=0.0,
                        provenance="model",
                        model_id="fake/topics",
                        model_revision="v1",
                        definition_hash="hash",
                        input_hash="input",
                        threshold=0.5,
                        generated_at="2026-01-01T00:00:00+00:00",
                    )
                ],
            )
    enrich_transcripts(
        tmp_path,
        FakeTranscriber(),
        ClipFilter(topics=("entrepreneurship",)),
    )
    with Catalog.open(tmp_path) as catalog:
        record = catalog.get("instagram", "A")
        assert semantic_document(record) == (
            "caption: startup story\ntranscript: hello multilingual world"
        )
        assert catalog.topic_names("instagram", "A") == ("entrepreneurship",)
        assert catalog.get_embedding("instagram", "A", "fake/embed", "v1") is None
        assert catalog.topic_names("instagram", "B") == ("uncategorized",)
        assert catalog.get_embedding("instagram", "B", "fake/embed", "v1") is not None
    report = semantic_index(tmp_path, FakeEmbedder())
    assert report.indexed == 1 and report.unchanged == 1
    categorize_library(tmp_path, FakeEmbedder())
    with Catalog.open(tmp_path) as catalog:
        assert catalog.topic_names("instagram", "A") == (
            "entrepreneurship",
            "learning",
        )


def test_catalog_reindex_preserves_transcript_and_remains_idempotent(tmp_path):
    from clipfetch.catalog import index_library

    _library(tmp_path, _record("A"))
    enrich_transcripts(tmp_path, FakeTranscriber())
    first = index_library(tmp_path)
    second = index_library(tmp_path)
    assert first.updated == 1 and second.unchanged == 1
    with Catalog.open(tmp_path) as catalog:
        assert catalog.get("instagram", "A").transcript_text == "hello multilingual world"


def test_missing_optional_extra_and_normalization(monkeypatch):
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    with pytest.raises(TranscriptionError, match=r'pip install "clipfetch\[transcribe\]"'):
        FasterWhisperTranscriber()
    assert normalize_transcript("  one\n two\tthree ") == "one two three"
