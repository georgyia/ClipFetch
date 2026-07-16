"""Incremental, local-only speech transcript enrichment."""

from __future__ import annotations

import hashlib
import importlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from clipfetch.catalog import Catalog, CatalogError, CatalogRecord
from clipfetch.errors import ClipFetchError
from clipfetch.library import ClipFilter, query_library

DEFAULT_TRANSCRIPT_MODEL = "base"
DEFAULT_TRANSCRIPT_REVISION = "faster-whisper-1.2.1"
DEFAULT_TRANSCRIPT_CACHE = Path.home() / ".cache" / "clipfetch" / "faster-whisper"


class TranscriptionError(ClipFetchError):
    """The optional local transcription workflow cannot start."""


class UnsupportedMedia(Exception):
    """A file has no supported audio stream/format."""


@dataclass(frozen=True)
class TranscriptResult:
    text: str
    language: str | None = None


class Transcriber(Protocol):
    model_id: str
    revision: str

    def transcribe(self, path: Path) -> TranscriptResult: ...


@dataclass(frozen=True)
class EnrichmentReport:
    selected: int
    completed: int
    skipped: int
    silent: int
    unsupported: int
    failed: int


class FasterWhisperTranscriber:
    """Lazy Faster-Whisper CPU/int8 adapter; PyAV handles media decoding."""

    revision = DEFAULT_TRANSCRIPT_REVISION

    def __init__(
        self,
        model: str = DEFAULT_TRANSCRIPT_MODEL,
        cache_dir: Path = DEFAULT_TRANSCRIPT_CACHE,
    ) -> None:
        self.model_id = f"faster-whisper/{model}"
        try:
            WhisperModel = importlib.import_module("faster_whisper").WhisperModel
        except ImportError as err:
            raise TranscriptionError(
                "Transcription support is not installed. Run: pip install "
                '"clipfetch[transcribe]" then retry this command.'
            ) from err
        cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._model = WhisperModel(
                model,
                device="cpu",
                compute_type="int8",
                download_root=str(cache_dir),
            )
        except Exception as err:
            raise TranscriptionError(f"could not load local transcription model: {err}") from err

    def transcribe(self, path: Path) -> TranscriptResult:
        try:
            segments, info = self._model.transcribe(
                str(path),
                beam_size=5,
                vad_filter=True,
            )
            text = " ".join(segment.text for segment in segments)
        except Exception as err:
            message = str(err).casefold()
            if any(
                marker in message
                for marker in (
                    "audio stream",
                    "invalid data",
                    "unsupported",
                    "could not open",
                    "no such file",
                )
            ):
                raise UnsupportedMedia(str(err)) from err
            raise
        return TranscriptResult(text=text, language=getattr(info, "language", None))


def enrich_transcripts(
    root: Path,
    transcriber: Transcriber,
    filters: ClipFilter | None = None,
    *,
    force: bool = False,
    on_progress: Callable[[int, int, str, CatalogRecord], None] | None = None,
) -> EnrichmentReport:
    """Process matching files independently and commit every terminal status."""
    result = query_library(root, filters)
    completed = skipped = silent = unsupported = failed = 0
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
            and record.transcript_source_hash == source_hash
            and record.transcript_model_id == transcriber.model_id
            and record.transcript_model_revision == transcriber.revision
            and record.transcript_status in {"complete", "silent", "unsupported"}
        )
        if unchanged:
            skipped += 1
            if on_progress:
                on_progress(index, total, "skipped", record)
            continue
        started = time.monotonic()
        try:
            transcript = transcriber.transcribe(path)
            text = normalize_transcript(transcript.text)
            status = "complete" if text else "silent"
            with Catalog.open(root) as catalog:
                catalog.set_transcript(
                    record.platform,
                    record.clip_id,
                    text=text or None,
                    language=transcript.language,
                    model_id=transcriber.model_id,
                    model_revision=transcriber.revision,
                    source_hash=source_hash,
                    processing_seconds=time.monotonic() - started,
                    status=status,
                )
            if status == "complete":
                completed += 1
            else:
                silent += 1
        except UnsupportedMedia as err:
            status = "unsupported"
            unsupported += 1
            with Catalog.open(root) as catalog:
                catalog.set_transcript(
                    record.platform,
                    record.clip_id,
                    text=None,
                    language=None,
                    model_id=transcriber.model_id,
                    model_revision=transcriber.revision,
                    source_hash=source_hash,
                    processing_seconds=time.monotonic() - started,
                    status=status,
                    error=str(err),
                )
        except KeyboardInterrupt:
            raise
        except Exception as err:
            status = "failed"
            failed += 1
            try:
                with Catalog.open(root) as catalog:
                    catalog.set_transcript(
                        record.platform,
                        record.clip_id,
                        text=None,
                        language=None,
                        model_id=transcriber.model_id,
                        model_revision=transcriber.revision,
                        source_hash=source_hash,
                        processing_seconds=time.monotonic() - started,
                        status=status,
                        error=str(err),
                    )
            except CatalogError:
                pass
        if on_progress:
            on_progress(index, total, status, record)
    return EnrichmentReport(total, completed, skipped, silent, unsupported, failed)


def normalize_transcript(value: str) -> str:
    """Collapse backend/segment whitespace without changing spoken content."""
    return " ".join(value.split())


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
