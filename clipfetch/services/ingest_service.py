"""Ingestion: turn a queued job into catalogued clips through a pluggable source provider.

The *flow* is provider-agnostic. A real provider (built later) will drive the browser stack; the
:class:`FakeSourceProvider` here produces deterministic clips with no network or credentials, so the
whole ingestion path — claim a job, fetch clips, write media, catalogue them, report progress,
complete or fail — is exercisable in ordinary tests.

Nothing here imports the browser stack, argparse, FastAPI, or the UI. Errors surfaced to callers
are :class:`IngestError` with safe, user-facing messages; unexpected failures are reported
generically so internals never reach the job's public error.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from clipfetch.appstate import AppState, Job
from clipfetch.catalog import Catalog, CatalogRecord

#: Default worker identity and lease when a caller does not supply one.
DEFAULT_OWNER = "clipfetch-worker"
DEFAULT_LEASE_SECONDS = 60.0

#: Job kinds this module knows how to run, and therefore the only kinds the API may accept.
#:
#: The runner owns this list rather than the API layer: a kind that can be enqueued but not run is
#: a job that sits in the queue forever, or — worse, before this was enforced — one that fell
#: through to the download path and harvested the feed instead. ``jobs_service`` re-exports this so
#: both ends stay in step by construction.
RUNNABLE_JOB_KINDS = ("download", "enrich")


class IngestError(RuntimeError):
    """A source-level failure with a message safe to show the user.

    ``code`` is a stable failure category (``authentication_required``, ``rate_limited``,
    ``source_unavailable``, ``unsupported_source``, or the default ``source_error``) that the job
    records as its public error code, so the UI can offer the right recovery action.
    """

    def __init__(self, message: str, *, code: str = "source_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SourceClip:
    """One clip produced by a source provider, ready to be written and catalogued.

    Provide exactly one of ``media`` (in-memory bytes, used by the offline fake) or ``media_path``
    (a file already downloaded to a temporary location, used by real providers so whole videos never
    sit in memory). ``run_ingest`` moves ``media_path`` into the library.
    """

    clip_id: str
    platform: str
    media: bytes | None
    source_url: str
    author: str | None = None
    caption: str | None = None
    likes: int | None = None
    views: int | None = None
    duration_seconds: float | None = None
    hashtags: tuple[str, ...] = ()
    media_path: Path | None = None


class SourceProvider(Protocol):
    """Yields clips for a source. Implementations must be pull-based so progress can be reported."""

    def fetch(self, permalink: str, count: int, quality: str | None) -> Iterator[SourceClip]: ...


@dataclass
class IngestResult:
    downloaded_ids: list[str] = field(default_factory=list)
    cancelled: bool = False

    @property
    def count(self) -> int:
        return len(self.downloaded_ids)


ProgressFn = Callable[[int, int, str], None]
CancelFn = Callable[[], bool]
#: Generates a poster for one catalogued clip. Injectable so tests use a fake instead of ffmpeg.
PosterFn = Callable[[Path, str, str], object]


def run_ingest(
    root: Path,
    *,
    permalink: str,
    count: int,
    quality: str | None,
    provider: SourceProvider,
    on_progress: ProgressFn | None = None,
    cancel_check: CancelFn | None = None,
    poster_fn: PosterFn | None = None,
) -> IngestResult:
    """Fetch up to ``count`` clips and catalogue them, reporting progress and honoring cancels.

    After the clips are written and the catalog connection closes, a poster is generated for each
    (best-effort — a thumbnail failure never fails a completed download). ``poster_fn`` is
    injectable so tests avoid ffmpeg; the default extracts a real frame via the poster service.
    """
    result = IngestResult()
    downloaded: list[tuple[str, str]] = []
    root.mkdir(parents=True, exist_ok=True)
    with Catalog.open(root) as catalog:
        for index, clip in enumerate(provider.fetch(permalink, count, quality)):
            if cancel_check is not None and cancel_check():
                result.cancelled = True
                break
            relative = f"{clip.platform}/{clip.clip_id}.mp4"
            dest = root / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            _write_media(clip, dest)
            stat = os.stat(dest)
            catalog.upsert(
                CatalogRecord(
                    platform=clip.platform,
                    clip_id=clip.clip_id,
                    relative_path=relative,
                    file_size=stat.st_size,
                    file_mtime_ns=stat.st_mtime_ns,
                    downloaded_at=_now_iso(),
                    source_url=clip.source_url,
                    author=clip.author,
                    caption=clip.caption,
                    likes=clip.likes,
                    metadata_state="complete",
                    available=True,
                    hashtags=clip.hashtags,
                    views=clip.views,
                    duration_seconds=clip.duration_seconds,
                )
            )
            result.downloaded_ids.append(clip.clip_id)
            downloaded.append((clip.platform, clip.clip_id))
            if on_progress is not None:
                on_progress(index + 1, count, "downloading")

    _generate_posters(root, downloaded, poster_fn=poster_fn, on_progress=on_progress, total=count)
    return result


def _generate_posters(
    root: Path,
    clips: list[tuple[str, str]],
    *,
    poster_fn: PosterFn | None,
    on_progress: ProgressFn | None,
    total: int,
) -> None:
    """Extract a poster frame for each downloaded clip. Runs after the catalog write connection is
    closed (poster generation opens its own read connection) and swallows every failure — a missing
    thumbnail must never turn a finished download into a failed job."""
    if not clips:
        return
    generate: PosterFn
    if poster_fn is not None:
        generate = poster_fn
    else:
        from clipfetch.services.poster_service import generate_poster

        generate = generate_poster
    if on_progress is not None:
        on_progress(len(clips), total, "posters")
    for platform, clip_id in clips:
        try:
            generate(root, platform, clip_id)
        except Exception:  # noqa: BLE001 - best-effort enrichment, never fatal
            continue


def process_next_job(
    appstate: AppState,
    root: Path | None,
    provider: SourceProvider,
    *,
    owner: str = DEFAULT_OWNER,
    lease_seconds: float = DEFAULT_LEASE_SECONDS,
    root_resolver: Callable[[Job], Path] | None = None,
) -> Job | None:
    """Claim and run one queued job. Returns the finished job, or ``None`` if the queue is empty.

    Pass ``root`` for a single-library caller, or ``root_resolver`` to derive the on-disk root from
    the claimed job (e.g. a worker draining jobs across libraries). Exactly one must resolve a path.
    """
    job = appstate.claim_job(owner, lease_seconds=lease_seconds)
    if job is None:
        return None
    if job.kind not in RUNNABLE_JOB_KINDS:
        # Never fall through to the download path: an unrunnable kind reaching this point means a
        # queue written by another version (or by hand), and running it as a download would do
        # something the user never asked for. It cannot succeed on a retry either, so it is final.
        return appstate.fail_job(
            job.id,
            owner,
            error_code="unsupported_job_kind",
            error_message=f"This version cannot run {job.kind} jobs.",
            retry=False,
        )
    job_root = root_resolver(job) if root_resolver is not None else root
    if job_root is None:  # pragma: no cover - guarded by callers
        raise ValueError("process_next_job needs a root or a root_resolver")

    def on_progress(current: int, total: int, phase: str) -> None:
        appstate.heartbeat_job(
            job.id, owner, lease_seconds=lease_seconds,
            progress_current=current, progress_total=total, phase=phase,
        )

    def cancelled() -> bool:
        return appstate.get_job(job.id).cancel_requested

    if job.kind == "enrich":
        return _run_enrich_job(appstate, job, job_root, owner, on_progress=on_progress)

    try:
        request = _parse_request(job.request_json)
        result = run_ingest(
            job_root,
            permalink=job.source_permalink or "",
            count=request.count,
            quality=request.quality,
            provider=provider,
            on_progress=on_progress,
            cancel_check=cancelled,
        )
    except IngestError as err:
        return appstate.fail_job(job.id, owner, error_code=err.code, error_message=str(err))
    except Exception:  # noqa: BLE001 - never leak internals into the public job error
        return appstate.fail_job(
            job.id, owner, error_code="ingest_failed",
            error_message="The download could not be completed.",
        )

    if result.cancelled:
        return appstate.cancel_job(job.id, owner)
    return appstate.complete_job(
        job.id, owner,
        result_json=json.dumps({"downloaded": result.count, "clip_ids": result.downloaded_ids}),
    )


def _run_enrich_job(
    appstate: AppState,
    job: Job,
    root: Path,
    owner: str,
    *,
    on_progress: Callable[[int, int, str], None],
) -> Job:
    """Add a transcript or comments to one clip.

    Kept beside the download path rather than in the worker, so *how a job of each kind is claimed,
    heartbeated, and finished* stays in one function — only the work in the middle differs.
    """
    from clipfetch.services import enrichment_jobs

    try:
        request = enrichment_jobs.EnrichRequest.parse(json.loads(job.request_json or "{}"))
    except (ValueError, TypeError) as err:
        # A malformed payload cannot become valid on a retry.
        return appstate.fail_job(
            job.id, owner, error_code="invalid_request", error_message=str(err), retry=False
        )

    try:
        result = enrichment_jobs.run_enrichment(root, request, on_progress=on_progress)
    except enrichment_jobs.EnrichmentUnavailable as err:
        # Missing extras and absent sign-ins do not fix themselves between attempts; the UI turns
        # the code into the right recovery action instead.
        return appstate.fail_job(
            job.id, owner, error_code=err.code, error_message=str(err), retry=False
        )
    except Exception:  # noqa: BLE001 - never leak internals into the public job error
        return appstate.fail_job(
            job.id,
            owner,
            error_code="enrichment_failed",
            error_message="The enrichment could not be completed.",
        )
    return appstate.complete_job(job.id, owner, result_json=json.dumps(result, ensure_ascii=False))


@dataclass(frozen=True)
class _ParsedRequest:
    count: int
    quality: str | None


def _parse_request(request_json: str) -> _ParsedRequest:
    try:
        raw = json.loads(request_json)
    except (ValueError, TypeError):
        raw = {}
    data = raw if isinstance(raw, dict) else {}
    count = data.get("count")
    quality = data.get("quality")
    return _ParsedRequest(
        count=count if isinstance(count, int) and count > 0 else 1,
        quality=quality if isinstance(quality, str) else None,
    )


def _write_media(clip: SourceClip, dest: Path) -> None:
    """Place a clip's media at ``dest``: move a downloaded file, or write in-memory bytes."""
    if clip.media_path is not None:
        import shutil

        shutil.move(str(clip.media_path), str(dest))
    elif clip.media is not None:
        dest.write_bytes(clip.media)
    else:  # pragma: no cover - a provider must supply one
        raise IngestError("The source produced a clip with no media.")


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


class FakeSourceProvider:
    """Deterministic, offline source: identical inputs yield identical clips and media bytes.

    Lets tests and a future demo mode exercise the full ingestion path with no network. Pass
    ``fail_after`` to simulate a mid-run source failure, or ``platform`` to pick the platform.
    """

    def __init__(self, *, platform: str = "instagram", fail_after: int | None = None) -> None:
        self._platform = platform
        self._fail_after = fail_after

    def fetch(self, permalink: str, count: int, quality: str | None) -> Iterator[SourceClip]:
        digest = hashlib.sha1(permalink.encode("utf-8")).hexdigest()[:8]
        for index in range(count):
            if self._fail_after is not None and index >= self._fail_after:
                raise IngestError("The source stopped responding.")
            clip_id = f"FAKE_{digest}_{index}"
            body = f"clipfetch-fake:{permalink}:{index}\n".encode()
            yield SourceClip(
                clip_id=clip_id,
                platform=self._platform,
                media=body,
                source_url=f"{permalink}#{index}",
                author=f"creator_{digest}",
                caption=f"Fake clip {index} for {permalink}",
                likes=1000 * (index + 1),
                views=10_000 * (index + 1),
                duration_seconds=float(15 + index),
                hashtags=("fake", self._platform),
            )
