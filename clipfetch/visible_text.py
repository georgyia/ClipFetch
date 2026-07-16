"""Bounded, resumable local visible-text extraction from video frames."""

from __future__ import annotations

import difflib
import hashlib
import importlib
import math
import time
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from clipfetch.catalog import Catalog, CatalogError, CatalogRecord, VisibleTextSegment
from clipfetch.errors import ClipFetchError
from clipfetch.library import ClipFilter, query_library

SAMPLE_INTERVAL_SECONDS = 2.0
MAX_SAMPLED_FRAMES = 30
MAX_DECODED_FRAMES_PER_SAMPLE = 120
MIN_CONFIDENCE = 0.85
DEDUPLICATION_SIMILARITY = 0.88
MAX_RETAINED_CHARACTERS = 2000
SAMPLE_POLICY = "one-per-2s,max-30,decode-max-120-per-sample,v1"
DEFAULT_MODEL_ID = "rapidocr/pp-ocrv6-small"
DEFAULT_MODEL_REVISION = "rapidocr-3.9.1/onnxruntime-cpu"


class VisibleTextError(ClipFetchError):
    """The optional local visible-text workflow cannot start."""


class UnsupportedMedia(Exception):
    """A file has no video stream or usable duration."""


class CorruptMedia(Exception):
    """A video or sampled frame could not be decoded."""


@dataclass(frozen=True)
class SampledFrame:
    timestamp_seconds: float
    image: Any


@dataclass(frozen=True)
class RecognizedLine:
    timestamp_seconds: float
    text: str
    confidence: float


@dataclass(frozen=True)
class VisibleTextResult:
    text: str
    segments: tuple[VisibleTextSegment, ...]
    confidence: float | None


@dataclass(frozen=True)
class EnrichmentReport:
    selected: int
    completed: int
    skipped: int
    empty: int
    unsupported: int
    corrupt: int
    failed: int


class Extractor(Protocol):
    model_id: str
    revision: str
    sample_policy: str

    def extract(self, path: Path) -> VisibleTextResult: ...


class PyAVFrameSampler:
    """Seek to a strictly bounded set of timestamps using packaged PyAV."""

    def __init__(self) -> None:
        try:
            self._av = importlib.import_module("av")
        except ImportError as err:
            raise VisibleTextError(
                'Visible-text support is not installed. Run: pip install "clipfetch[ocr]" '
                "then retry this command."
            ) from err

    def sample(self, path: Path) -> tuple[SampledFrame, ...]:
        try:
            with self._av.open(str(path)) as container:
                stream = next((item for item in container.streams if item.type == "video"), None)
                if stream is None:
                    raise UnsupportedMedia("no video stream")
                duration = _duration_seconds(container, stream, self._av)
                if duration is None or duration <= 0:
                    raise UnsupportedMedia("video duration is unavailable")
                return tuple(
                    self._sample_frame(container, stream, target)
                    for target in sample_timestamps(duration)
                )
        except (UnsupportedMedia, CorruptMedia):
            raise
        except Exception as err:
            raise CorruptMedia(str(err) or type(err).__name__) from err

    def _sample_frame(self, container: Any, stream: Any, target: float) -> SampledFrame:
        try:
            time_base = float(stream.time_base)
            container.seek(max(0, int(target / time_base)), stream=stream, backward=True)
            selected = None
            timestamp = target
            for index, frame in enumerate(container.decode(stream)):
                selected = frame
                if frame.pts is not None:
                    timestamp = max(0.0, float(frame.pts * stream.time_base))
                if timestamp >= target or index + 1 >= MAX_DECODED_FRAMES_PER_SAMPLE:
                    break
            if selected is None:
                raise CorruptMedia("sampled frame could not be decoded")
            return SampledFrame(timestamp, selected.to_ndarray(format="bgr24"))
        except CorruptMedia:
            raise
        except Exception as err:
            raise CorruptMedia(str(err) or type(err).__name__) from err


class RapidOCRExtractor:
    """Lazy RapidOCR/ONNX adapter; models and inference remain fully local."""

    model_id = DEFAULT_MODEL_ID
    revision = DEFAULT_MODEL_REVISION
    sample_policy = SAMPLE_POLICY

    def __init__(self, sampler: PyAVFrameSampler | None = None) -> None:
        try:
            RapidOCR = importlib.import_module("rapidocr").RapidOCR
        except ImportError as err:
            raise VisibleTextError(
                'Visible-text support is not installed. Run: pip install "clipfetch[ocr]" '
                "then retry this command."
            ) from err
        self._sampler = sampler or PyAVFrameSampler()
        try:
            self._engine = RapidOCR()
        except Exception as err:
            raise VisibleTextError(f"could not load the local OCR models: {err}") from err

    def extract(self, path: Path) -> VisibleTextResult:
        lines: list[RecognizedLine] = []
        for frame in self._sampler.sample(path):
            try:
                result = self._engine(frame.image)
                texts = result.txts or ()
                scores = result.scores or ()
            except Exception as err:
                raise CorruptMedia(str(err) or type(err).__name__) from err
            lines.extend(
                RecognizedLine(frame.timestamp_seconds, str(text), float(score))
                for text, score in zip(texts, scores)
            )
        return retain_lines(lines)


def sample_timestamps(duration_seconds: float) -> tuple[float, ...]:
    """Return the only timestamps the sampler may inspect."""
    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise UnsupportedMedia("video duration is unavailable")
    count = min(MAX_SAMPLED_FRAMES, max(1, math.ceil(duration_seconds / SAMPLE_INTERVAL_SECONDS)))
    return tuple(index * SAMPLE_INTERVAL_SECONDS for index in range(count))


def retain_lines(lines: Iterable[RecognizedLine]) -> VisibleTextResult:
    """Normalize, confidence-filter, similarity-dedupe, and hard-cap OCR output."""
    retained: list[VisibleTextSegment] = []
    for line in lines:
        text = normalize_visible_text(line.text)
        if not text or not math.isfinite(line.confidence) or line.confidence < MIN_CONFIDENCE:
            continue
        candidate = VisibleTextSegment(line.timestamp_seconds, text, line.confidence)
        duplicate_at = next(
            (
                index
                for index, existing in enumerate(retained)
                if _similarity(existing.text, candidate.text) >= DEDUPLICATION_SIMILARITY
            ),
            None,
        )
        if duplicate_at is None:
            retained.append(candidate)
        elif candidate.confidence > retained[duplicate_at].confidence:
            retained[duplicate_at] = candidate

    capped: list[VisibleTextSegment] = []
    used = 0
    for item in sorted(retained, key=lambda segment: segment.timestamp_seconds):
        separator = 1 if capped else 0
        remaining = MAX_RETAINED_CHARACTERS - used - separator
        if remaining <= 0:
            break
        text = item.text[:remaining].rstrip()
        if not text:
            break
        capped.append(VisibleTextSegment(item.timestamp_seconds, text, item.confidence))
        used += separator + len(text)
    combined = "\n".join(item.text for item in capped)
    confidence = (
        sum(item.confidence for item in capped) / len(capped) if capped else None
    )
    return VisibleTextResult(combined, tuple(capped), confidence)


def normalize_visible_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def enrich_visible_text(
    root: Path,
    extractor: Extractor,
    filters: ClipFilter | None = None,
    *,
    force: bool = False,
    on_progress: Callable[[int, int, str, CatalogRecord], None] | None = None,
) -> EnrichmentReport:
    """Process files independently, committing each complete terminal outcome."""
    result = query_library(root, filters)
    completed = skipped = empty = unsupported = corrupt = failed = 0
    total = len(result.clips)
    for index, record in enumerate(result.clips, start=1):
        path = root / record.relative_path
        try:
            source_hash = _file_hash(path)
        except OSError:
            failed += 1
            if on_progress:
                on_progress(index, total, "failed", record)
            continue
        unchanged = (
            not force
            and record.visible_text_source_hash == source_hash
            and record.visible_text_model_id == extractor.model_id
            and record.visible_text_model_revision == extractor.revision
            and record.visible_text_sample_policy == extractor.sample_policy
            and record.visible_text_status in {"complete", "empty", "unsupported", "corrupt"}
        )
        if unchanged:
            skipped += 1
            if on_progress:
                on_progress(index, total, "skipped", record)
            continue

        started = time.monotonic()
        try:
            visible = extractor.extract(path)
            status = "complete" if visible.text else "empty"
            with Catalog.open(root) as catalog:
                catalog.set_visible_text(
                    record.platform,
                    record.clip_id,
                    text=visible.text or None,
                    segments=visible.segments,
                    confidence=visible.confidence,
                    model_id=extractor.model_id,
                    model_revision=extractor.revision,
                    source_hash=source_hash,
                    sample_policy=extractor.sample_policy,
                    processing_seconds=time.monotonic() - started,
                    status=status,
                )
            if status == "complete":
                completed += 1
            else:
                empty += 1
        except KeyboardInterrupt:
            raise
        except (UnsupportedMedia, CorruptMedia) as err:
            status = "unsupported" if isinstance(err, UnsupportedMedia) else "corrupt"
            unsupported += int(status == "unsupported")
            corrupt += int(status == "corrupt")
            _store_failure(root, record, extractor, source_hash, started, status, err)
        except Exception as err:
            status = "failed"
            failed += 1
            try:
                _store_failure(root, record, extractor, source_hash, started, status, err)
            except CatalogError:
                pass
        if on_progress:
            on_progress(index, total, status, record)
    return EnrichmentReport(total, completed, skipped, empty, unsupported, corrupt, failed)


def _store_failure(
    root: Path,
    record: CatalogRecord,
    extractor: Extractor,
    source_hash: str,
    started: float,
    status: str,
    error: Exception,
) -> None:
    with Catalog.open(root) as catalog:
        catalog.set_visible_text(
            record.platform,
            record.clip_id,
            text=None,
            segments=(),
            confidence=None,
            model_id=extractor.model_id,
            model_revision=extractor.revision,
            source_hash=source_hash,
            sample_policy=extractor.sample_policy,
            processing_seconds=time.monotonic() - started,
            status=status,
            error=str(error),
        )


def _duration_seconds(container: Any, stream: Any, av_module: Any) -> float | None:
    if stream.duration is not None and stream.time_base is not None:
        return float(stream.duration * stream.time_base)
    if container.duration is not None:
        return float(container.duration / av_module.time_base)
    return None


def _similarity(left: str, right: str) -> float:
    return difflib.SequenceMatcher(None, left.casefold(), right.casefold()).ratio()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
