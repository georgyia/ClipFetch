"""Background job worker: drains the queue and reaps stale leases alongside the API server.

The worker runs on a daemon thread started and stopped by the FastAPI application lifespan (see
``clipfetch.api.app``). Each tick it reaps expired leases so a crashed run recovers, then — when a
:class:`~clipfetch.services.ingest_service.SourceProvider` is configured — claims and processes one
job. Housekeeping and job failures are logged and swallowed so a single bad job never kills the
loop; the job's own public error is recorded by :func:`ingest_service.process_next_job`.

Wiring a real, browser-driven provider is a later step. Until then the server runs with no provider
(jobs stay queued, honestly reflecting that downloads are not yet automated), or with the offline
:class:`~clipfetch.services.ingest_service.FakeSourceProvider` in ``clipfetch web --demo``.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable

from clipfetch.appstate import AppState, Job
from clipfetch.services import ingest_service
from clipfetch.services.ingest_service import SourceProvider

logger = logging.getLogger("clipfetch.worker")

#: How long to wait between ticks when the queue is empty.
DEFAULT_POLL_SECONDS = 1.0

RootResolver = Callable[[Job], Path]


def library_root_resolver(appstate: AppState) -> RootResolver:
    """Resolve a claimed job's on-disk library root from its ``library_id``."""

    def resolve(job: Job) -> Path:
        return Path(appstate.get_library(job.library_id).root_path)

    return resolve


class Worker:
    """A daemon-thread loop that reaps leases and processes queued jobs.

    ``provider`` may be ``None``: the worker still reaps expired leases (cheap housekeeping) but
    does not claim jobs, so nothing is downloaded. Start and stop are idempotent.
    """

    def __init__(
        self,
        appstate: AppState,
        *,
        provider: SourceProvider | None,
        root_resolver: RootResolver | None = None,
        poll_seconds: float = DEFAULT_POLL_SECONDS,
        owner: str = ingest_service.DEFAULT_OWNER,
    ) -> None:
        self._appstate = appstate
        self._provider = provider
        self._root_resolver = root_resolver or library_root_resolver(appstate)
        self._poll_seconds = poll_seconds
        self._owner = owner
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="clipfetch-worker", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout)

    def _loop(self) -> None:
        while not self._stop.is_set():
            worked = self.tick()
            if not worked:
                # Sleep interruptibly so stop() returns promptly.
                self._stop.wait(self._poll_seconds)

    def tick(self) -> bool:
        """Run one unit of work. Returns ``True`` when a job ran, to keep the loop busy."""
        try:
            self._appstate.reap_expired_leases()
        except Exception:  # noqa: BLE001 - housekeeping must never kill the loop
            logger.exception("lease reaping failed")
        if self._provider is None:
            return False
        try:
            job = ingest_service.process_next_job(
                self._appstate,
                None,
                self._provider,
                owner=self._owner,
                root_resolver=self._root_resolver,
            )
        except Exception:  # noqa: BLE001 - a bad job must never kill the loop
            logger.exception("job processing failed")
            return False
        return job is not None
