from __future__ import annotations

import json

from clipfetch.appstate import JOB_CANCELLED, JOB_FAILED, JOB_SUCCEEDED, AppState
from clipfetch.catalog import Catalog
from clipfetch.library import ClipFilter, query_library
from clipfetch.services import ingest_service
from clipfetch.services.ingest_service import FakeSourceProvider, run_ingest


def _appstate(tmp_path):
    return AppState.open(tmp_path / "appstate.sqlite3")


def test_run_ingest_writes_media_and_catalogs(tmp_path):
    root = tmp_path / "lib"
    result = run_ingest(
        root, permalink="https://x/p/1", count=3, quality=None, provider=FakeSourceProvider()
    )
    assert result.count == 3
    assert not result.cancelled
    # Media files exist and are catalogued.
    for clip_id in result.downloaded_ids:
        assert (root / "instagram" / f"{clip_id}.mp4").is_file()
    assert query_library(root, ClipFilter()).matched == 3


def test_process_next_job_completes(tmp_path):
    root = tmp_path / "lib"
    appstate = _appstate(tmp_path)
    job = appstate.enqueue_job(
        "lib", "download", json.dumps({"count": 2}), source_permalink="https://x/p/1"
    )

    finished = ingest_service.process_next_job(appstate, root, FakeSourceProvider())
    assert finished is not None
    assert finished.id == job.id
    assert finished.state == JOB_SUCCEEDED
    result = json.loads(finished.result_json)
    assert result["downloaded"] == 2
    assert len(result["clip_ids"]) == 2

    # Progress events were recorded.
    types = [event.event_type for event in appstate.list_job_events(job.id)]
    assert "progress" in types
    assert types[-1] == "succeeded"


def test_process_next_job_returns_none_when_empty(tmp_path):
    appstate = _appstate(tmp_path)
    assert ingest_service.process_next_job(appstate, tmp_path / "lib", FakeSourceProvider()) is None


def test_source_failure_is_recorded_safely(tmp_path):
    root = tmp_path / "lib"
    appstate = _appstate(tmp_path)
    appstate.enqueue_job(
        "lib", "download", json.dumps({"count": 3}),
        source_permalink="https://x/p/1", max_attempts=1,
    )
    finished = ingest_service.process_next_job(
        appstate, root, FakeSourceProvider(fail_after=1)
    )
    assert finished is not None
    assert finished.state == JOB_FAILED
    assert finished.public_error_code == "source_error"
    assert finished.public_error_message == "The source stopped responding."


def test_run_ingest_honors_cancellation(tmp_path):
    root = tmp_path / "lib"
    # Cancel after the first clip: exactly one is written, then the run stops.
    calls = {"n": 0}

    def cancel_check() -> bool:
        calls["n"] += 1
        return calls["n"] > 1

    result = run_ingest(
        root,
        permalink="https://x/p/1",
        count=5,
        quality=None,
        provider=FakeSourceProvider(),
        cancel_check=cancel_check,
    )
    assert result.cancelled is True
    assert result.count == 1


def test_cancelled_queued_job_is_not_processed(tmp_path):
    root = tmp_path / "lib"
    appstate = _appstate(tmp_path)
    job = appstate.enqueue_job(
        "lib", "download", json.dumps({"count": 5}), source_permalink="https://x/p/1"
    )
    # Cancelling a queued job finalizes it immediately, so the worker never claims it.
    cancelled = appstate.request_job_cancel(job.id)
    assert cancelled.state == JOB_CANCELLED
    assert ingest_service.process_next_job(appstate, root, FakeSourceProvider()) is None


def test_fake_provider_is_deterministic(tmp_path):
    a = list(FakeSourceProvider().fetch("https://x/p/1", 2, None))
    b = list(FakeSourceProvider().fetch("https://x/p/1", 2, None))
    assert [clip.clip_id for clip in a] == [clip.clip_id for clip in b]
    assert [clip.media for clip in a] == [clip.media for clip in b]


def test_ingested_clip_is_playable_through_catalog(tmp_path):
    root = tmp_path / "lib"
    run_ingest(
        root, permalink="https://x/p/1", count=1, quality=None, provider=FakeSourceProvider()
    )
    with Catalog.open(root) as catalog:
        records = catalog.all()
    assert len(records) == 1
    assert records[0].available is True
