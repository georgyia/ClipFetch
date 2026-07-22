from __future__ import annotations

import pytest

from clipfetch.appstate import (
    JOB_CANCELLED,
    JOB_FAILED,
    JOB_QUEUED,
    JOB_RUNNING,
    JOB_SUCCEEDED,
    AppState,
    AppStateError,
)


@pytest.fixture
def appstate(tmp_path):
    state = AppState.open(tmp_path / "appstate.sqlite3")
    yield state
    state.close()


def test_migration_reaches_version_3(appstate):
    assert appstate.schema_version == 3


def test_enqueue_claim_complete(appstate):
    job = appstate.enqueue_job("lib", "download", '{"url": "x"}', source_permalink="x")
    assert job.state == JOB_QUEUED
    assert job.attempt == 0

    claimed = appstate.claim_job("worker-1", lease_seconds=30)
    assert claimed is not None
    assert claimed.id == job.id
    assert claimed.state == JOB_RUNNING
    assert claimed.lease_owner == "worker-1"
    assert claimed.attempt == 1
    assert claimed.started_at is not None

    done = appstate.complete_job(job.id, "worker-1", result_json='{"clip_id": "IG1"}')
    assert done.state == JOB_SUCCEEDED
    assert done.result_json == '{"clip_id": "IG1"}'
    assert done.lease_owner is None


def test_claim_is_single_flight(appstate):
    appstate.enqueue_job("lib", "download", "{}")
    first = appstate.claim_job("w1", lease_seconds=30)
    second = appstate.claim_job("w2", lease_seconds=30)
    assert first is not None
    assert second is None  # only one queued job; the second worker gets nothing


def test_claim_orders_by_creation(appstate):
    a = appstate.enqueue_job("lib", "download", "{}")
    b = appstate.enqueue_job("lib", "download", "{}")
    assert appstate.claim_job("w", lease_seconds=30).id == a.id
    assert appstate.claim_job("w", lease_seconds=30).id == b.id


def test_failure_retries_with_backoff_then_gives_up(appstate):
    job = appstate.enqueue_job("lib", "download", "{}", max_attempts=2)

    appstate.claim_job("w", lease_seconds=30)
    retried = appstate.fail_job(job.id, "w", error_code="rate_limited", error_message="429")
    assert retried.state == JOB_QUEUED
    assert retried.available_at is not None  # backoff scheduled
    assert retried.public_error_code == "rate_limited"

    # Not claimable until the backoff elapses.
    assert appstate.claim_job("w", lease_seconds=30) is None

    # Force the backoff to have elapsed and claim again; the second failure is terminal.
    appstate._connection.execute("UPDATE jobs SET available_at = NULL WHERE id = ?", (job.id,))
    appstate._connection.commit()
    appstate.claim_job("w", lease_seconds=30)
    final = appstate.fail_job(job.id, "w", error_code="rate_limited", error_message="429")
    assert final.state == JOB_FAILED
    assert final.finished_at is not None


def test_heartbeat_updates_progress_and_extends_lease(appstate):
    job = appstate.enqueue_job("lib", "download", "{}")
    appstate.claim_job("w", lease_seconds=30)
    beat = appstate.heartbeat_job(
        job.id, "w", lease_seconds=60, progress_current=3, progress_total=10, phase="downloading"
    )
    assert beat.progress_current == 3
    assert beat.progress_total == 10
    assert beat.phase == "downloading"


def test_heartbeat_rejects_wrong_owner(appstate):
    job = appstate.enqueue_job("lib", "download", "{}")
    appstate.claim_job("w1", lease_seconds=30)
    with pytest.raises(AppStateError):
        appstate.heartbeat_job(job.id, "intruder", lease_seconds=30)


def test_cancel_queued_job_immediately(appstate):
    job = appstate.enqueue_job("lib", "download", "{}")
    cancelled = appstate.request_job_cancel(job.id)
    assert cancelled.state == JOB_CANCELLED
    # A cancelled job is never claimed.
    assert appstate.claim_job("w", lease_seconds=30) is None


def test_cancel_running_job_is_cooperative(appstate):
    job = appstate.enqueue_job("lib", "download", "{}")
    appstate.claim_job("w", lease_seconds=30)
    flagged = appstate.request_job_cancel(job.id)
    assert flagged.state == JOB_RUNNING
    assert flagged.cancel_requested is True
    finalized = appstate.cancel_job(job.id, "w")
    assert finalized.state == JOB_CANCELLED


def test_expired_lease_is_reaped(appstate):
    job = appstate.enqueue_job("lib", "download", "{}")
    appstate.claim_job("w", lease_seconds=30)
    # Expire the lease in the past.
    appstate._connection.execute(
        "UPDATE jobs SET lease_expires_at = '2000-01-01T00:00:00+00:00' WHERE id = ?", (job.id,)
    )
    appstate._connection.commit()

    assert appstate.reap_expired_leases() == 1
    reaped = appstate.get_job(job.id)
    assert reaped.state == JOB_QUEUED
    assert reaped.lease_owner is None
    # Another worker can now pick it up.
    assert appstate.claim_job("w2", lease_seconds=30) is not None


def test_events_are_recorded_in_order(appstate):
    job = appstate.enqueue_job("lib", "download", "{}")
    appstate.claim_job("w", lease_seconds=30)
    appstate.heartbeat_job(job.id, "w", lease_seconds=30, progress_current=1)
    appstate.complete_job(job.id, "w")
    events = appstate.list_job_events(job.id)
    types = [event.event_type for event in events]
    assert types == ["enqueued", "claimed", "progress", "succeeded"]
    assert [event.sequence for event in events] == [1, 2, 3, 4]


def test_list_jobs_scoped_by_library(appstate):
    appstate.enqueue_job("lib-a", "download", "{}")
    appstate.enqueue_job("lib-b", "download", "{}")
    assert len(appstate.list_jobs("lib-a")) == 1
    assert len(appstate.list_jobs()) == 2
