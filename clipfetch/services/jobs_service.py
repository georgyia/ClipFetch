"""Job API service: sanitized job views and enqueue/browse/cancel over the app-state queue.

Wraps :class:`~clipfetch.appstate.AppState`'s job queue for the web layer. A :class:`JobView` is
the only job shape that leaves the process: it exposes the user-facing source permalink, lifecycle
state, phase/progress, attempt counters, and the *sanitized* public error — never the raw request
payload, device paths, cookies, or internal exceptions.

Enqueuing a download is idempotent per source: submitting a permalink that already has an active
(queued or running) job returns that job rather than creating a duplicate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from clipfetch.appstate import (
    JOB_QUEUED,
    JOB_RUNNING,
    AppState,
    AppStateError,
    Job,
    JobEvent,
)

#: Job kinds the API accepts.
JOB_KINDS = ("download", "enrich")

_ACTIVE_STATES = frozenset({JOB_QUEUED, JOB_RUNNING})


class JobServiceError(RuntimeError):
    """A job request was invalid (unknown kind, missing fields, unknown job)."""


@dataclass(frozen=True)
class JobView:
    """Sanitized, serializable view of a queued/running/finished job."""

    id: str
    kind: str
    state: str
    source_permalink: str | None
    phase: str | None
    progress_current: int | None
    progress_total: int | None
    attempt: int
    max_attempts: int
    cancel_requested: bool
    error_code: str | None
    error_message: str | None
    result: dict[str, Any] | None
    created_at: str
    started_at: str | None
    finished_at: str | None
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "state": self.state,
            "source_permalink": self.source_permalink,
            "phase": self.phase,
            "progress_current": self.progress_current,
            "progress_total": self.progress_total,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "cancel_requested": self.cancel_requested,
            "error": (
                None
                if self.error_code is None
                else {"code": self.error_code, "message": self.error_message}
            ),
            "result": self.result,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "updated_at": self.updated_at,
        }


def _safe_result(result_json: str | None) -> dict[str, Any] | None:
    """Parse a job's stored result, dropping anything that isn't a plain JSON object."""
    if not result_json:
        return None
    try:
        value = json.loads(result_json)
    except (ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def view(job: Job) -> JobView:
    return JobView(
        id=job.id,
        kind=job.kind,
        state=job.state,
        source_permalink=job.source_permalink,
        phase=job.phase,
        progress_current=job.progress_current,
        progress_total=job.progress_total,
        attempt=job.attempt,
        max_attempts=job.max_attempts,
        cancel_requested=job.cancel_requested,
        error_code=job.public_error_code,
        error_message=job.public_error_message,
        result=_safe_result(job.result_json),
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        updated_at=job.updated_at,
    )


def event_to_dict(event: JobEvent) -> dict[str, Any]:
    return {
        "sequence": event.sequence,
        "type": event.event_type,
        "phase": event.phase,
        "message": event.message,
        "progress_current": event.progress_current,
        "progress_total": event.progress_total,
        "created_at": event.created_at,
    }


def _active_job_for(appstate: AppState, library_id: str, source_permalink: str) -> Job | None:
    for job in appstate.list_jobs(library_id, limit=200):
        if (
            job.kind == "download"
            and job.source_permalink == source_permalink
            and job.state in _ACTIVE_STATES
        ):
            return job
    return None


def enqueue(
    appstate: AppState,
    library_id: str,
    kind: str,
    *,
    source_permalink: str | None,
    request: dict[str, Any],
) -> tuple[JobView, bool]:
    """Enqueue a job. Returns (view, created); ``created`` is False when an active job is reused."""
    if kind not in JOB_KINDS:
        raise JobServiceError(f"unknown job kind: {kind}")
    # ``None`` means the field was omitted; ``""`` is the explicit "your feed" sentinel
    # (see browser_source._target_from and the Downloads UI).
    if kind == "download" and source_permalink is None:
        raise JobServiceError("a download job requires a source url")

    if kind == "download" and source_permalink is not None:
        existing = _active_job_for(appstate, library_id, source_permalink)
        if existing is not None:
            return view(existing), False

    job = appstate.enqueue_job(
        library_id,
        kind,
        json.dumps(request, ensure_ascii=False),
        source_permalink=source_permalink,
    )
    return view(job), True


def get(appstate: AppState, job_id: str) -> JobView:
    try:
        return view(appstate.get_job(job_id))
    except AppStateError as err:
        raise JobServiceError(str(err)) from err


def list_jobs(appstate: AppState, library_id: str, *, limit: int = 50) -> list[JobView]:
    return [view(job) for job in appstate.list_jobs(library_id, limit=limit)]


def cancel(appstate: AppState, job_id: str) -> JobView:
    try:
        appstate.get_job(job_id)
    except AppStateError as err:
        raise JobServiceError(str(err)) from err
    return view(appstate.request_job_cancel(job_id))


def events(appstate: AppState, job_id: str, *, after_sequence: int = 0) -> list[dict[str, Any]]:
    rows = appstate.list_job_events(job_id, after_sequence=after_sequence)
    return [event_to_dict(event) for event in rows]
