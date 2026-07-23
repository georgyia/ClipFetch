"""Job endpoints: enqueue downloads/enrichment, browse, cancel, and follow progress.

Progress can be followed two ways with the same event data: a Server-Sent Events stream
(``/stream``) for live updates, and a plain polling endpoint (``/events``) as the low-frequency
fallback. Both replay from a caller-supplied sequence so no event is missed across reconnects.

FastAPI evaluates these route signatures at runtime, so this module intentionally does not use
``from __future__ import annotations`` and uses ``Optional[...]`` for Python 3.9 compatibility.
"""

import json
import time
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Header, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from clipfetch.api.dependencies import ActiveLibraryDep, AppStateDep
from clipfetch.api.errors import ApiException
from clipfetch.appstate import JOB_CANCELLED, JOB_FAILED, JOB_SUCCEEDED
from clipfetch.services import jobs_service
from clipfetch.services.jobs_service import JobServiceError

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])

_TERMINAL = {JOB_SUCCEEDED, JOB_FAILED, JOB_CANCELLED}
# Bound a live stream so a forgotten client cannot hold a worker thread forever.
_STREAM_MAX_TICKS = 600
_STREAM_POLL_SECONDS = 0.5


class EnqueueJobRequest(BaseModel):
    kind: str = "download"
    url: Optional[str] = Field(default=None, max_length=2048)
    count: int = Field(default=1, ge=1, le=200)
    quality: Optional[str] = Field(default=None, max_length=32)


@router.get("")
def list_jobs(
    appstate: AppStateDep,
    library: ActiveLibraryDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    views = jobs_service.list_jobs(appstate, library.id, limit=limit)
    return {"jobs": [view.to_dict() for view in views]}


@router.post("", status_code=201)
def enqueue_job(
    body: EnqueueJobRequest, appstate: AppStateDep, library: ActiveLibraryDep, response: Response
) -> dict[str, Any]:
    request = {"count": body.count, "quality": body.quality}
    try:
        view, created = jobs_service.enqueue(
            appstate, library.id, body.kind, source_permalink=body.url, request=request
        )
    except JobServiceError as err:
        raise ApiException(422, "invalid_job", str(err)) from err
    # Idempotent reuse of an active job returns 200, not 201.
    response.status_code = 201 if created else 200
    return view.to_dict()


@router.get("/{job_id}")
def get_job(job_id: str, appstate: AppStateDep, library: ActiveLibraryDep) -> dict[str, Any]:
    try:
        return jobs_service.get(appstate, job_id).to_dict()
    except JobServiceError as err:
        raise ApiException(404, "job_not_found", str(err)) from err


@router.post("/{job_id}/cancel")
def cancel_job(job_id: str, appstate: AppStateDep, library: ActiveLibraryDep) -> dict[str, Any]:
    try:
        return jobs_service.cancel(appstate, job_id).to_dict()
    except JobServiceError as err:
        raise ApiException(404, "job_not_found", str(err)) from err


@router.get("/{job_id}/events")
def job_events(
    job_id: str,
    appstate: AppStateDep,
    library: ActiveLibraryDep,
    after: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    try:
        job = jobs_service.get(appstate, job_id)
    except JobServiceError as err:
        raise ApiException(404, "job_not_found", str(err)) from err
    return {
        "job": job.to_dict(),
        "events": jobs_service.events(appstate, job_id, after_sequence=after),
    }


@router.get("/{job_id}/stream")
def job_stream(
    job_id: str,
    appstate: AppStateDep,
    library: ActiveLibraryDep,
    after: Annotated[int, Query(ge=0)] = 0,
    last_event_id: Annotated[Optional[str], Header()] = None,
) -> StreamingResponse:
    try:
        jobs_service.get(appstate, job_id)
    except JobServiceError as err:
        raise ApiException(404, "job_not_found", str(err)) from err

    start = after
    if last_event_id:
        try:
            start = max(start, int(last_event_id))
        except ValueError:
            pass

    def stream() -> Any:
        cursor = start
        for _ in range(_STREAM_MAX_TICKS):
            for event in jobs_service.events(appstate, job_id, after_sequence=cursor):
                cursor = event["sequence"]
                yield f"id: {cursor}\nevent: {event['type']}\ndata: {json.dumps(event)}\n\n"
            state = jobs_service.get(appstate, job_id).state
            if state in _TERMINAL:
                yield f"event: end\ndata: {json.dumps({'state': state})}\n\n"
                return
            time.sleep(_STREAM_POLL_SECONDS)

    return StreamingResponse(stream(), media_type="text/event-stream")
