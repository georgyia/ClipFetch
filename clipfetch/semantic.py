"""Local semantic indexing and cosine search with an injectable embedder."""

from __future__ import annotations

import hashlib
import importlib
import math
import struct
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from clipfetch.catalog import Catalog, CatalogError, CatalogRecord, EmbeddingRecord
from clipfetch.errors import ClipFetchError
from clipfetch.library import ClipFilter, query_library

DEFAULT_MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_MODEL_REVISION = "fastembed-0.8.0/mean-pooling/Qdrant-onnx-Q@faf4aa4"
DEFAULT_DIMENSION = 384
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "clipfetch" / "fastembed"


class SemanticError(ClipFetchError):
    """Semantic indexing/search could not produce a trustworthy result."""


class Embedder(Protocol):
    """Minimal seam used by normal tests and the optional FastEmbed adapter."""

    model_id: str
    revision: str

    def embed(self, texts: Sequence[str]) -> Iterable[Sequence[float]]: ...


@dataclass(frozen=True)
class SemanticIndexReport:
    scanned: int
    indexed: int
    unchanged: int
    empty: int


@dataclass(frozen=True)
class SemanticMatch:
    record: CatalogRecord
    score: float


@dataclass(frozen=True)
class SemanticSearchResult:
    matches: tuple[SemanticMatch, ...]
    considered: int
    unindexed: int


class FastEmbedder:
    """Lazy optional adapter; importing ClipFetch never imports ONNX/FastEmbed."""

    model_id = DEFAULT_MODEL_ID
    revision = DEFAULT_MODEL_REVISION

    def __init__(self, cache_dir: Path = DEFAULT_CACHE_DIR) -> None:
        try:
            TextEmbedding = importlib.import_module("fastembed").TextEmbedding
        except ImportError as err:
            raise SemanticError(
                'Semantic support is not installed. Run: pip install "clipfetch[semantic]" '
                "then retry this command."
            ) from err
        cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._model = TextEmbedding(
                model_name=self.model_id,
                cache_dir=str(cache_dir),
            )
        except Exception as err:
            raise SemanticError(
                f"Could not load {self.model_id}: {err}. Retry this command after checking "
                f"the model cache at {cache_dir}."
            ) from err

    def embed(self, texts: Sequence[str]) -> Iterable[Sequence[float]]:
        return self._model.embed(list(texts))


def semantic_document(record: CatalogRecord) -> str | None:
    """Compose a stable labeled document from local metadata only."""
    parts = []
    if record.caption and record.caption.strip():
        parts.append(f"caption: {record.caption.strip()}")
    if record.hashtags:
        parts.append("hashtags: " + " ".join(f"#{tag}" for tag in record.hashtags))
    if record.transcript_text and record.transcript_text.strip():
        parts.append(f"transcript: {record.transcript_text.strip()}")
    if record.comment_text and record.comment_text.strip():
        parts.append(f"comments: {record.comment_text.strip()}")
    return "\n".join(parts) or None


def semantic_index(
    root: Path,
    embedder: Embedder,
    *,
    batch_size: int = 32,
    on_progress: Callable[[int, int], None] | None = None,
) -> SemanticIndexReport:
    """Incrementally embed changed documents, committing only complete batches."""
    if batch_size < 1:
        raise SemanticError("batch size must be at least 1")
    if not root.is_dir():
        raise CatalogError(f"library directory does not exist: {root.resolve()}")

    indexed = unchanged = empty = 0
    with Catalog.open(root) as catalog:
        records = [
            record
            for record in catalog.all()
            if record.available and (root / record.relative_path).is_file()
        ]
        existing_vectors = catalog.embeddings_for(embedder.model_id, embedder.revision)
        dimensions = {entry.dimension for entry in existing_vectors}
        if len(dimensions) > 1:
            raise SemanticError("stored vectors mix dimensions for the selected model")
        expected_dimension = next(iter(dimensions), None)
        pending: list[tuple[CatalogRecord, str, str]] = []
        for record in records:
            document = semantic_document(record)
            if not document:
                catalog.delete_embedding(
                    record.platform,
                    record.clip_id,
                    embedder.model_id,
                    embedder.revision,
                )
                empty += 1
                if on_progress:
                    on_progress(indexed + unchanged + empty, len(records))
                continue
            input_hash = hashlib.sha256(document.encode("utf-8")).hexdigest()
            current = catalog.get_embedding(
                record.platform,
                record.clip_id,
                embedder.model_id,
                embedder.revision,
            )
            if (
                current
                and current.input_hash == input_hash
                and current.dimension > 0
                and len(current.vector) == current.dimension * 4
            ):
                unchanged += 1
                if on_progress:
                    on_progress(indexed + unchanged + empty, len(records))
                continue
            pending.append((record, document, input_hash))
            if len(pending) == batch_size:
                added, expected_dimension = _embed_batch(
                    catalog, pending, embedder, expected_dimension
                )
                indexed += added
                pending = []
                if on_progress:
                    on_progress(indexed + unchanged + empty, len(records))
        if pending:
            added, expected_dimension = _embed_batch(
                catalog, pending, embedder, expected_dimension
            )
            indexed += added
            if on_progress:
                on_progress(indexed + unchanged + empty, len(records))
    return SemanticIndexReport(len(records), indexed, unchanged, empty)


def semantic_search(
    root: Path,
    query: str,
    embedder: Embedder,
    filters: ClipFilter | None = None,
    *,
    limit: int = 20,
) -> SemanticSearchResult:
    """Rank indexed, filter-matching clips by in-process cosine similarity."""
    if not query.strip():
        raise SemanticError("search query must not be empty")
    if limit < 1:
        raise SemanticError("limit must be at least 1")
    filtered = query_library(root, filters)
    records = {(record.platform, record.clip_id): record for record in filtered.clips}
    if not records:
        return SemanticSearchResult(matches=(), considered=0, unindexed=0)
    with Catalog.open(root) as catalog:
        stored = catalog.embeddings_for(embedder.model_id, embedder.revision)
    input_hashes = {
        key: hashlib.sha256(document.encode("utf-8")).hexdigest()
        for key, record in records.items()
        if (document := semantic_document(record)) is not None
    }
    relevant = [
        entry
        for entry in stored
        if entry.input_hash == input_hashes.get((entry.platform, entry.clip_id))
    ]
    if not relevant:
        raise SemanticError(
            "No compatible semantic index is available. Run: "
            f"clipfetch library semantic-index {root}"
        )
    try:
        query_vectors = list(embedder.embed([query.strip()]))
    except Exception as err:
        raise SemanticError(f"local query embedding failed: {err}") from err
    if len(query_vectors) != 1:
        raise SemanticError("embedder returned an unexpected number of query vectors")
    query_vector = _normalize_vector(query_vectors[0])
    dimensions = {entry.dimension for entry in relevant}
    if dimensions != {len(query_vector)}:
        raise SemanticError(
            "semantic index dimension does not match the selected model; re-run semantic-index"
        )
    matches = []
    for entry in relevant:
        vector = _unpack_vector(entry.vector, entry.dimension)
        score = sum(left * right for left, right in zip(query_vector, vector))
        matches.append(
            SemanticMatch(records[(entry.platform, entry.clip_id)], max(-1.0, min(1.0, score)))
        )
    matches.sort(key=lambda match: (-match.score, match.record.platform, match.record.clip_id))
    return SemanticSearchResult(
        matches=tuple(matches[:limit]),
        considered=len(records),
        unindexed=len(records) - len(relevant),
    )


def _embed_batch(
    catalog: Catalog,
    pending: list[tuple[CatalogRecord, str, str]],
    embedder: Embedder,
    expected_dimension: int | None,
) -> tuple[int, int]:
    try:
        vectors = list(embedder.embed([document for _, document, _ in pending]))
    except Exception as err:
        raise SemanticError(
            f"local embedding failed; this batch was not stored and can be retried: {err}"
        ) from err
    if len(vectors) != len(pending):
        raise SemanticError("embedder returned an incomplete batch; no batch data was stored")
    normalized = [_normalize_vector(vector) for vector in vectors]
    dimensions = {len(vector) for vector in normalized}
    if len(dimensions) != 1:
        raise SemanticError("embedder returned mixed vector dimensions; no batch data was stored")
    dimension = next(iter(dimensions))
    if expected_dimension is not None and dimension != expected_dimension:
        raise SemanticError(
            "embedder dimension changed for the same model revision; no batch data was stored"
        )
    generated_at = datetime.now(timezone.utc).isoformat()
    records = [
        EmbeddingRecord(
            platform=record.platform,
            clip_id=record.clip_id,
            model_id=embedder.model_id,
            model_revision=embedder.revision,
            input_hash=input_hash,
            dimension=dimension,
            vector=_pack_vector(vector),
            generated_at=generated_at,
        )
        for (record, _, input_hash), vector in zip(pending, normalized)
    ]
    catalog.store_embeddings(records)
    return len(records), dimension


def _normalize_vector(values: Sequence[float]) -> tuple[float, ...]:
    try:
        vector = tuple(float(value) for value in values)
    except (TypeError, ValueError) as err:
        raise SemanticError("embedder returned a non-numeric vector") from err
    if not vector or any(not math.isfinite(value) for value in vector):
        raise SemanticError("embedder returned an empty or non-finite vector")
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        raise SemanticError("embedder returned a zero vector")
    return tuple(value / norm for value in vector)


def _pack_vector(vector: Sequence[float]) -> bytes:
    return struct.pack(f"<{len(vector)}f", *vector)


def _unpack_vector(value: bytes, dimension: int) -> tuple[float, ...]:
    if dimension < 1 or len(value) != dimension * 4:
        raise SemanticError("stored semantic vector is corrupt")
    return struct.unpack(f"<{dimension}f", value)
