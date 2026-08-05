from __future__ import annotations

import json
from pathlib import Path

import pytest

from clipfetch.appstate import JOB_FAILED, JOB_QUEUED, JOB_SUCCEEDED, AppState
from clipfetch.catalog import Catalog, index_library
from clipfetch.services import enrichment_jobs, ingest_service
from clipfetch.services.enrichment_jobs import EnrichmentUnavailable, EnrichRequest
from clipfetch.services.ingest_service import FakeSourceProvider
from clipfetch.transcription import TranscriptResult


class FakeTranscriber:
    """Stands in for Whisper so the real status logic runs without a model download."""

    model_id = "fake/base"
    revision = "v1"

    def __init__(self, text: str = "hello there") -> None:
        self._text = text

    def transcribe(self, path: Path) -> TranscriptResult:
        return TranscriptResult(text=self._text, language="en")


def _library(tmp_path: Path) -> Path:
    root = tmp_path / "reels"
    root.mkdir()
    (root / "reel_001_ABC.mp4").write_bytes(b"video")
    index_library(root)
    return root


def _appstate(tmp_path: Path) -> AppState:
    return AppState.open(tmp_path / "appstate.sqlite3")


def _transcribe_with(transcriber):
    """Drive the real enrich_transcripts, so statuses and provenance are the production ones."""

    def run(root, record, progress):
        from clipfetch.transcription import enrich_transcripts

        report = enrich_transcripts(root, transcriber, records=[record])
        return {"completed": report.completed, "silent": report.silent}

    return run


def test_request_parsing_rejects_what_cannot_be_run():
    assert EnrichRequest.parse({"clip_id": "ABC", "target": "transcript"}).target == "transcript"
    with pytest.raises(ValueError, match="clip id"):
        EnrichRequest.parse({"target": "transcript"})
    with pytest.raises(ValueError, match="target must be"):
        EnrichRequest.parse({"clip_id": "ABC", "target": "vibes"})


def test_enrichment_writes_a_transcript_through_the_shared_enricher(tmp_path):
    root = _library(tmp_path)
    result = enrichment_jobs.run_enrichment(
        root,
        EnrichRequest("ABC", "transcript"),
        transcribe=_transcribe_with(FakeTranscriber()),
    )

    assert result == {"clip_id": "ABC", "target": "transcript", "completed": 1, "silent": 0}
    with Catalog.open(root) as catalog:
        record = catalog.get("instagram", "ABC")
    # Provenance comes from the enricher, not from this service — one implementation, one truth.
    assert record.transcript_text == "hello there"
    assert record.transcript_status == "complete"
    assert record.transcript_model_id == "fake/base"


def test_an_unknown_clip_is_reported_as_such(tmp_path):
    root = _library(tmp_path)
    with pytest.raises(EnrichmentUnavailable) as err:
        enrichment_jobs.run_enrichment(root, EnrichRequest("NOPE", "transcript"))
    assert err.value.code == "clip_not_found"


def test_the_worker_runs_an_enrichment_job_end_to_end(tmp_path, monkeypatch):
    root = _library(tmp_path)
    appstate = _appstate(tmp_path)
    monkeypatch.setattr(
        enrichment_jobs, "_default_transcribe", _transcribe_with(FakeTranscriber())
    )
    job = appstate.enqueue_job(
        "lib", "enrich", json.dumps({"clip_id": "ABC", "target": "transcript"})
    )

    finished = ingest_service.process_next_job(appstate, root, FakeSourceProvider())
    assert finished is not None and finished.id == job.id
    assert finished.state == JOB_SUCCEEDED
    assert json.loads(finished.result_json)["target"] == "transcript"
    # An enrichment must never download anything.
    assert [path.name for path in root.rglob("*.mp4")] == ["reel_001_ABC.mp4"]


def test_a_missing_prerequisite_fails_the_job_terminally(tmp_path, monkeypatch):
    """Installing an extra is not something a retry can accomplish, so backoff would only stall."""
    root = _library(tmp_path)
    appstate = _appstate(tmp_path)

    def unavailable(root_, record, progress):
        raise EnrichmentUnavailable("not installed", code="transcription_unavailable")

    monkeypatch.setattr(enrichment_jobs, "_default_transcribe", unavailable)
    appstate.enqueue_job("lib", "enrich", json.dumps({"clip_id": "ABC", "target": "transcript"}))

    finished = ingest_service.process_next_job(appstate, root, FakeSourceProvider())
    assert finished.state == JOB_FAILED
    assert finished.public_error_code == "transcription_unavailable"
    assert ingest_service.process_next_job(appstate, root, FakeSourceProvider()) is None


def test_an_unexpected_failure_never_leaks_internals(tmp_path, monkeypatch):
    """Unlike a missing extra, an unexpected error may be transient, so it keeps its retries."""
    root = _library(tmp_path)
    appstate = _appstate(tmp_path)

    def explode(root_, record, progress):
        raise RuntimeError(f"boom at /Users/someone/secret/{record.relative_path}")

    monkeypatch.setattr(enrichment_jobs, "_default_transcribe", explode)
    appstate.enqueue_job("lib", "enrich", json.dumps({"clip_id": "ABC", "target": "transcript"}))

    finished = ingest_service.process_next_job(appstate, root, FakeSourceProvider())
    assert finished.public_error_code == "enrichment_failed"
    assert finished.state == JOB_QUEUED  # scheduled for another attempt
    message = finished.public_error_message or ""
    assert "secret" not in message and "boom" not in message


def test_a_malformed_payload_is_terminal_rather_than_retried(tmp_path):
    root = _library(tmp_path)
    appstate = _appstate(tmp_path)
    appstate.enqueue_job("lib", "enrich", json.dumps({"target": "transcript"}))

    finished = ingest_service.process_next_job(appstate, root, FakeSourceProvider())
    assert finished.state == JOB_FAILED
    assert finished.public_error_code == "invalid_request"
    assert ingest_service.process_next_job(appstate, root, FakeSourceProvider()) is None


def test_progress_is_reported_while_the_job_runs(tmp_path, monkeypatch):
    root = _library(tmp_path)
    appstate = _appstate(tmp_path)
    monkeypatch.setattr(
        enrichment_jobs, "_default_transcribe", _transcribe_with(FakeTranscriber())
    )
    job = appstate.enqueue_job(
        "lib", "enrich", json.dumps({"clip_id": "ABC", "target": "transcript"})
    )

    ingest_service.process_next_job(appstate, root, FakeSourceProvider())
    events = [event.event_type for event in appstate.list_job_events(job.id)]
    assert "progress" in events and events[-1] == "succeeded"
