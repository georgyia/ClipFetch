"""The background worker drains the queue, recovers stale leases, and starts/stops cleanly."""

from __future__ import annotations

import time
from pathlib import Path

from clipfetch.appstate import JOB_QUEUED, JOB_RUNNING, JOB_SUCCEEDED, AppState
from clipfetch.library import ClipFilter, query_library
from clipfetch.services.ingest_service import FakeSourceProvider
from clipfetch.worker import Worker


def _register(appstate: AppState, root: Path) -> str:
    entry = appstate.register_library("Reels", root)
    return entry.id


def _wait_for(predicate, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_worker_processes_a_queued_job(tmp_path):
    root = tmp_path / "reels"
    root.mkdir()
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    library_id = _register(appstate, root)
    job = appstate.enqueue_job(
        library_id, "download", '{"count": 3}', source_permalink="https://x/p/1"
    )

    worker = Worker(appstate, provider=FakeSourceProvider(), poll_seconds=0.02)
    worker.start()
    try:
        assert _wait_for(lambda: appstate.get_job(job.id).state == JOB_SUCCEEDED)
    finally:
        worker.stop()

    assert query_library(root, ClipFilter()).matched == 3


def test_worker_resolves_root_per_job_library(tmp_path):
    """Two libraries: each job's clips land in its own library, chosen by the resolver."""
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    root_a.mkdir()
    root_b.mkdir()
    id_a = _register(appstate, root_a)
    id_b = _register(appstate, root_b)
    job_a = appstate.enqueue_job(id_a, "download", '{"count": 1}', source_permalink="https://x/a")
    job_b = appstate.enqueue_job(id_b, "download", '{"count": 2}', source_permalink="https://x/b")

    worker = Worker(appstate, provider=FakeSourceProvider(), poll_seconds=0.02)
    worker.start()
    try:
        assert _wait_for(
            lambda: appstate.get_job(job_a.id).state == JOB_SUCCEEDED
            and appstate.get_job(job_b.id).state == JOB_SUCCEEDED
        )
    finally:
        worker.stop()

    assert query_library(root_a, ClipFilter()).matched == 1
    assert query_library(root_b, ClipFilter()).matched == 2


def test_worker_without_provider_only_reaps_leases(tmp_path):
    """With no provider, a job stays queued; an expired lease is still recovered."""
    root = tmp_path / "reels"
    root.mkdir()
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    library_id = _register(appstate, root)
    job = appstate.enqueue_job(library_id, "download", '{"count": 1}')

    # A crashed run leaves a running job with an already-expired lease.
    appstate.claim_job("dead-worker", lease_seconds=-1.0)
    assert appstate.get_job(job.id).state == JOB_RUNNING

    worker = Worker(appstate, provider=None, poll_seconds=0.02)
    worker.start()
    try:
        assert _wait_for(lambda: appstate.get_job(job.id).state == JOB_QUEUED)
    finally:
        worker.stop()


def test_worker_start_stop_is_idempotent(tmp_path):
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    worker = Worker(appstate, provider=None, poll_seconds=0.02)
    worker.start()
    worker.start()  # second start is a no-op, not a second thread
    worker.stop()
    worker.stop()  # stopping twice is safe
