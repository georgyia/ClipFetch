"""Run one clip's enrichment as a background job: transcribe it, or fetch its comments.

Both jobs are thin drivers over the enrichment the CLI already performs — ``enrich_transcripts``
and ``enrich_comments`` — rather than second implementations. Everything about *what a status
means*, when a clip is skipped, and how a failure is recorded stays in those modules, so the app
and the CLI can never disagree about the state of a clip.

The heavy backends (Whisper, a signed-in browser context) are injected, defaulting to lazy factory
functions that import them only when a real job runs. Tests drive the whole path with fakes and
never touch a model download or a network.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clipfetch.catalog import CatalogError, CatalogRecord
from clipfetch.library import find_clip

#: What an enrichment job can be asked to add.
ENRICH_TARGETS = ("transcript", "comments")

#: Comments fetched per clip by a UI-triggered job. The CLI can ask for more; this is a sensible
#: bound for a one-click action, well under ``comments.HARD_MAX_COMMENTS``.
DEFAULT_MAX_COMMENTS = 30

ProgressFn = Callable[[int, int, str], None]
#: ``(root, record, on_progress) -> status counts``
Transcribe = Callable[[Path, CatalogRecord, ProgressFn], dict[str, Any]]
#: ``(root, record, max_comments, on_progress) -> status counts``
FetchComments = Callable[[Path, CatalogRecord, int, ProgressFn], dict[str, Any]]


class EnrichmentUnavailable(RuntimeError):
    """The enrichment cannot run here — a missing extra, or no signed-in session.

    ``code`` is a stable category the job records as its public error code so the UI can offer the
    right recovery action instead of a dead end.
    """

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class EnrichRequest:
    clip_id: str
    target: str

    @classmethod
    def parse(cls, raw: dict[str, Any]) -> EnrichRequest:
        clip_id = raw.get("clip_id")
        target = raw.get("target")
        if not isinstance(clip_id, str) or not clip_id.strip():
            raise ValueError("an enrichment job needs a clip id")
        if target not in ENRICH_TARGETS:
            raise ValueError(f"target must be one of: {', '.join(ENRICH_TARGETS)}")
        return cls(clip_id.strip(), target)


def run_enrichment(
    root: Path,
    request: EnrichRequest,
    *,
    on_progress: ProgressFn | None = None,
    transcribe: Transcribe | None = None,
    fetch_comments: FetchComments | None = None,
) -> dict[str, Any]:
    """Enrich one clip and return a small result summary for the job record."""
    progress = on_progress or (lambda current, total, phase: None)
    try:
        record = find_clip(root, request.clip_id)
    except CatalogError as err:
        raise EnrichmentUnavailable(str(err), code="clip_not_found") from err

    progress(0, 1, request.target)
    if request.target == "transcript":
        runner = transcribe or _default_transcribe
        outcome = runner(root, record, progress)
    else:
        runner_comments = fetch_comments or _default_fetch_comments
        outcome = runner_comments(root, record, DEFAULT_MAX_COMMENTS, progress)
    progress(1, 1, "done")
    return {"clip_id": record.clip_id, "target": request.target, **outcome}


def _default_transcribe(
    root: Path, record: CatalogRecord, progress: ProgressFn
) -> dict[str, Any]:
    """Transcribe one clip with the real local model, or explain why it cannot run."""
    from clipfetch.transcription import (
        FasterWhisperTranscriber,
        TranscriptionError,
        enrich_transcripts,
    )

    try:
        transcriber = FasterWhisperTranscriber()
    except TranscriptionError as err:
        raise EnrichmentUnavailable(str(err), code="transcription_unavailable") from err

    report = enrich_transcripts(
        root,
        transcriber,
        records=[record],
        on_progress=lambda index, total, status, _record: progress(index, total, status),
    )
    return {
        "completed": report.completed,
        "silent": report.silent,
        "unsupported": report.unsupported,
        "failed": report.failed,
        "skipped": report.skipped,
    }


def _default_fetch_comments(
    root: Path, record: CatalogRecord, max_comments: int, progress: ProgressFn
) -> dict[str, Any]:
    """Fetch one clip's comments through the signed-in browser profile.

    Unlike transcription, this needs a live session: the job refuses up front rather than failing
    deep inside a request, so the UI can offer *Connect account* instead of a retry that cannot
    work.
    """
    from clipfetch import session
    from clipfetch.comments import InstagramCommentBackend, enrich_comments
    from clipfetch.platforms import BY_KEY

    platform = BY_KEY.get(record.platform)
    if platform is None or record.platform != "instagram":
        raise EnrichmentUnavailable(
            f"Comments can only be fetched for Instagram clips, not {record.platform}.",
            code="unsupported_source",
        )

    with session.authenticated_session(platform) as context:
        if not session.has_session_cookie(context, platform):
            raise EnrichmentUnavailable(
                "Connect your Instagram account before fetching comments.",
                code="authentication_required",
            )
        report = enrich_comments(
            root,
            InstagramCommentBackend(context),
            [record],
            max_comments=max_comments,
            on_progress=lambda index, total, status, _record: progress(index, total, status),
        )
    return {
        "completed": report.completed,
        "empty": report.empty,
        "disabled": report.disabled,
        "deleted": report.deleted,
        "unavailable": report.unavailable,
        "failed": report.failed,
        "skipped": report.skipped,
    }
