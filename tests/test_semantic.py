import sys
from pathlib import Path

import pytest

from clipfetch.catalog import Catalog, CatalogRecord
from clipfetch.library import ClipFilter
from clipfetch.semantic import (
    FastEmbedder,
    SemanticError,
    semantic_document,
    semantic_index,
    semantic_search,
)


class FakeEmbedder:
    model_id = "test/multilingual"
    revision = "fixture-v1"

    def __init__(self, dimension=3, fail_call=None):
        self.dimension = dimension
        self.fail_call = fail_call
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))
        if self.fail_call == len(self.calls):
            raise RuntimeError("interrupted")
        vectors = []
        for text in texts:
            lowered = text.casefold()
            if any(word in lowered for word in ("startup", "entrepreneur", "emprendimiento")):
                base = [1.0, 0.0, 0.0]
            elif any(word in lowered for word in ("space", "nasa", "კოსმოს")):
                base = [0.0, 1.0, 0.0]
            else:
                base = [0.0, 0.0, 1.0]
            vectors.append(base[: self.dimension] + [0.5] * max(0, self.dimension - 3))
        return vectors


def _record(
    ident: str,
    caption: str | None,
    *,
    likes: int | None = None,
    hashtags: tuple[str, ...] = (),
) -> CatalogRecord:
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
        metadata_state="sidecar-v2",
        hashtags=hashtags,
    )


def _library(tmp_path: Path, *records: CatalogRecord) -> Path:
    with Catalog.open(tmp_path) as catalog:
        for record in records:
            catalog.upsert(record)
            (tmp_path / record.relative_path).write_bytes(b"video")
    return tmp_path


def test_semantic_document_is_labeled_and_empty_metadata_stays_unindexed():
    assert semantic_document(_record("A", " Build a company ", hashtags=("startup",))) == (
        "caption: Build a company\nhashtags: #startup"
    )
    assert semantic_document(_record("B", None)) is None


def test_index_batches_persists_and_second_run_does_no_embedding(tmp_path):
    _library(
        tmp_path,
        _record("A", "startup advice"),
        _record("B", "space science"),
        _record("EMPTY", None),
    )
    embedder = FakeEmbedder()
    report = semantic_index(tmp_path, embedder, batch_size=1)
    assert (report.scanned, report.indexed, report.unchanged, report.empty) == (3, 2, 0, 1)
    assert len(embedder.calls) == 2

    unchanged_embedder = FakeEmbedder()
    second = semantic_index(tmp_path, unchanged_embedder, batch_size=10)
    assert (second.indexed, second.unchanged, second.empty) == (0, 2, 1)
    assert unchanged_embedder.calls == []
    with Catalog.open(tmp_path) as catalog:
        stored = catalog.embeddings_for(embedder.model_id, embedder.revision)
        assert len(stored) == 2
        assert {entry.dimension for entry in stored} == {3}
        assert all(len(entry.vector) == 12 for entry in stored)


def test_changed_input_only_recomputes_changed_clip(tmp_path):
    original = _record("A", "startup advice")
    _library(tmp_path, original, _record("B", "space science"))
    semantic_index(tmp_path, FakeEmbedder())
    with Catalog.open(tmp_path) as catalog:
        catalog.upsert(_record("A", "space startup advice"))

    stale_safe = semantic_search(tmp_path, "startup", FakeEmbedder())
    assert [match.record.clip_id for match in stale_safe.matches] == ["B"]
    assert stale_safe.unindexed == 1

    embedder = FakeEmbedder()
    report = semantic_index(tmp_path, embedder)
    assert (report.indexed, report.unchanged) == (1, 1)
    assert len(embedder.calls) == 1 and len(embedder.calls[0]) == 1


def test_document_becoming_empty_removes_its_old_vector(tmp_path):
    _library(tmp_path, _record("A", "startup"))
    embedder = FakeEmbedder()
    semantic_index(tmp_path, embedder)
    with Catalog.open(tmp_path) as catalog:
        catalog.upsert(_record("A", None))
    report = semantic_index(tmp_path, FakeEmbedder())
    assert report.empty == 1
    with Catalog.open(tmp_path) as catalog:
        assert catalog.embeddings_for(embedder.model_id, embedder.revision) == []


def test_interrupted_batches_resume_without_half_written_vectors(tmp_path):
    _library(
        tmp_path,
        _record("A", "startup"),
        _record("B", "space"),
        _record("C", "cooking"),
    )
    interrupted = FakeEmbedder(fail_call=2)
    with pytest.raises(SemanticError, match="can be retried: interrupted"):
        semantic_index(tmp_path, interrupted, batch_size=1)
    with Catalog.open(tmp_path) as catalog:
        assert len(catalog.embeddings_for(interrupted.model_id, interrupted.revision)) == 1

    resumed = FakeEmbedder()
    report = semantic_index(tmp_path, resumed, batch_size=2)
    assert (report.indexed, report.unchanged) == (2, 1)
    with Catalog.open(tmp_path) as catalog:
        assert len(catalog.embeddings_for(resumed.model_id, resumed.revision)) == 3


def test_incomplete_batch_is_not_stored(tmp_path):
    _library(tmp_path, _record("A", "startup"), _record("B", "space"))

    class Incomplete(FakeEmbedder):
        def embed(self, texts):
            return [[1.0, 0.0, 0.0]]

    embedder = Incomplete()
    with pytest.raises(SemanticError, match="incomplete batch"):
        semantic_index(tmp_path, embedder, batch_size=2)
    with Catalog.open(tmp_path) as catalog:
        assert catalog.embeddings_for(embedder.model_id, embedder.revision) == []


def test_search_ranking_ties_and_metadata_filter(tmp_path):
    _library(
        tmp_path,
        _record("B", "startup guide", likes=2_000_000),
        _record("A", "entrepreneurship", likes=1_500_000),
        _record("SPACE", "space science", likes=5_000_000),
        _record("LOW", "startup basics", likes=10),
    )
    embedder = FakeEmbedder()
    semantic_index(tmp_path, embedder)
    result = semantic_search(
        tmp_path,
        "emprendimiento",
        FakeEmbedder(),
        filters=ClipFilter(min_likes=1_000_000),
    )
    assert [match.record.clip_id for match in result.matches] == ["A", "B", "SPACE"]
    assert result.matches[0].score == pytest.approx(1.0)
    assert result.matches[1].score == pytest.approx(1.0)


def test_dimension_and_model_revision_mismatches_never_mix(tmp_path):
    _library(tmp_path, _record("A", "startup"))
    semantic_index(tmp_path, FakeEmbedder(dimension=3))
    with pytest.raises(SemanticError, match="dimension"):
        semantic_search(tmp_path, "startup", FakeEmbedder(dimension=2))

    other = FakeEmbedder()
    other.revision = "other-revision"
    with pytest.raises(SemanticError, match="semantic index"):
        semantic_search(tmp_path, "startup", other)

    with Catalog.open(tmp_path) as catalog:
        catalog.upsert(_record("A", "changed startup caption"))
    with pytest.raises(SemanticError, match="dimension changed"):
        semantic_index(tmp_path, FakeEmbedder(dimension=2))
    with Catalog.open(tmp_path) as catalog:
        stored = catalog.get_embedding("instagram", "A", "test/multilingual", "fixture-v1")
        assert stored is not None and stored.dimension == 3


def test_empty_filtered_search_does_not_invoke_embedder(tmp_path):
    _library(tmp_path, _record("A", "startup", likes=10))
    semantic_index(tmp_path, FakeEmbedder())
    embedder = FakeEmbedder()
    result = semantic_search(
        tmp_path, "startup", embedder, filters=ClipFilter(min_likes=1_000_000)
    )
    assert result.matches == () and embedder.calls == []


def test_missing_optional_extra_has_exact_install_command(monkeypatch):
    monkeypatch.setitem(sys.modules, "fastembed", None)
    with pytest.raises(SemanticError, match=r'pip install "clipfetch\[semantic\]"'):
        FastEmbedder()
