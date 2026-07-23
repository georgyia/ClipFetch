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


class IngestError(RuntimeError):
    """A source-level failure with a message safe to show the user."""


@dataclass(frozen=True)
class SourceClip:
    """One clip produced by a source provider, ready to be written and catalogued."""

    clip_id: str
    platform: str
    media: bytes
    source_url: str
    author: str | None = None
    caption: str | None = None
    likes: int | None = None
    views: int | None = None
    duration_seconds: float | None = None
    hashtags: tuple[str, ...] = ()


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


def run_ingest(
    root: Path,
    *,
    permalink: str,
    count: int,
    quality: str | None,
    provider: SourceProvider,
    on_progress: ProgressFn | None = None,
    cancel_check: CancelFn | None = None,
) -> IngestResult:
    """Fetch up to ``count`` clips and catalogue them, reporting progress and honoring cancels."""
    result = IngestResult()
    root.mkdir(parents=True, exist_ok=True)
    with Catalog.open(root) as catalog:
        for index, clip in enumerate(provider.fetch(permalink, count, quality)):
            if cancel_check is not None and cancel_check():
                result.cancelled = True
                break
            relative = f"{clip.platform}/{clip.clip_id}.mp4"
            media_path = root / relative
            media_path.parent.mkdir(parents=True, exist_ok=True)
            media_path.write_bytes(clip.media)
            stat = os.stat(media_path)
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
            if on_progress is not None:
                on_progress(index + 1, count, "downloading")
    return result


def process_next_job(
    appstate: AppState,
    root: Path,
    provider: SourceProvider,
    *,
    owner: str = DEFAULT_OWNER,
    lease_seconds: float = DEFAULT_LEASE_SECONDS,
) -> Job | None:
    """Claim and run one queued job. Returns the finished job, or ``None`` if the queue is empty."""
    job = appstate.claim_job(owner, lease_seconds=lease_seconds)
    if job is None:
        return None

    def on_progress(current: int, total: int, phase: str) -> None:
        appstate.heartbeat_job(
            job.id, owner, lease_seconds=lease_seconds,
            progress_current=current, progress_total=total, phase=phase,
        )

    def cancelled() -> bool:
        return appstate.get_job(job.id).cancel_requested

    try:
        request = _parse_request(job.request_json)
        result = run_ingest(
            root,
            permalink=job.source_permalink or "",
            count=request.count,
            quality=request.quality,
            provider=provider,
            on_progress=on_progress,
            cancel_check=cancelled,
        )
    except IngestError as err:
        return appstate.fail_job(job.id, owner, error_code="source_error", error_message=str(err))
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
