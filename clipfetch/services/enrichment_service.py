"""Read a clip's stored enrichment: its speech transcript and its captured comments.

The clip contract reports *whether* a clip has a transcript or comments but never inlines the
bodies — they are unbounded, and a rail of twenty cards should not carry twenty transcripts. This
service is the other half of that boundary: the bodies, fetched one clip at a time, bounded, and
stripped of anything that should not leave the process.

What is deliberately not exposed: the stored ``transcript_error`` / ``comment_error`` strings. Both
hold ``str(exception)`` from a backend that can name local paths (see
:mod:`clipfetch.transcription` and :mod:`clipfetch.comments`). Callers get the enricher's stable
``status`` instead, which is what a UI needs to explain the situation anyway.
"""

from __future__ import annotations

from pathlib import Path

from clipfetch.catalog import Catalog
from clipfetch.contracts import CommentPage, CommentView, TranscriptView
from clipfetch.library import find_clip

#: Response cap for a transcript body. A short-form clip transcribes to a few kilobytes; this is
#: generous for the longest plausible one while keeping a single response bounded.
MAX_TRANSCRIPT_CHARACTERS = 100_000

DEFAULT_COMMENT_LIMIT = 50
#: Matches ``clipfetch.comments.HARD_MAX_COMMENTS``: never more than one capture's worth per page.
MAX_COMMENT_LIMIT = 100


def get_transcript(root: Path, clip_id: str) -> TranscriptView:
    """Return one clip's transcript, or raise ``CatalogError`` if the clip is unknown.

    A clip that was never transcribed is not an error: it comes back with ``status=None`` and no
    text, which is what distinguishes "not enriched yet" from "transcribed, and it is silent".
    """
    record = find_clip(root, clip_id)
    text = record.transcript_text
    truncated = text is not None and len(text) > MAX_TRANSCRIPT_CHARACTERS
    return TranscriptView(
        clip_id=record.clip_id,
        status=record.transcript_status,
        text=text[:MAX_TRANSCRIPT_CHARACTERS] if text is not None else None,
        language=record.transcript_language,
        model_id=record.transcript_model_id,
        model_revision=record.transcript_model_revision,
        updated_at=record.transcript_updated_at,
        truncated=truncated,
        character_count=len(text) if text is not None else 0,
    )


def list_comments(
    root: Path, clip_id: str, *, limit: int = DEFAULT_COMMENT_LIMIT, offset: int = 0
) -> CommentPage:
    """Return a bounded slice of one clip's captured comments, oldest-captured first."""
    record = find_clip(root, clip_id)
    page_size = max(1, min(limit, MAX_COMMENT_LIMIT))
    start = max(0, offset)
    with Catalog.open(root) as catalog:
        stored = catalog.comments_for(record.platform, record.clip_id)
    window = stored[start : start + page_size]
    end = start + len(window)
    return CommentPage(
        items=tuple(CommentView(id=item.comment_id, text=item.text) for item in window),
        total=len(stored),
        status=record.comment_status,
        retrieved_at=record.comment_retrieved_at,
        next_offset=end if end < len(stored) else None,
    )
