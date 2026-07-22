"""Playback progress service.

Wraps the device-local :class:`~clipfetch.appstate.AppState` playback table with a small, stable
view and the resume/completion policy shared by the API and (later) any other client. Progress is
per active library and never leaves the device beyond this contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from clipfetch.appstate import AppState, PlaybackEntry

#: A clip counts as finished once played at least this fraction of its known duration.
COMPLETE_FRACTION = 0.95
#: Positions below this are treated as "just started" and do not offer a resume point.
RESUME_MIN_MS = 3000


@dataclass(frozen=True)
class PlaybackView:
    """Serializable playback state for one clip, including the derived resume point."""

    clip_id: str
    position_ms: int
    duration_ms: int | None
    completed: bool
    resume_position_ms: int
    play_count: int
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_id": self.clip_id,
            "position_ms": self.position_ms,
            "duration_ms": self.duration_ms,
            "completed": self.completed,
            "resume_position_ms": self.resume_position_ms,
            "play_count": self.play_count,
            "updated_at": self.updated_at,
        }


def _resume_ms(position_ms: int, duration_ms: int | None, completed: bool) -> int:
    """Where playback should pick up: nowhere if finished or barely started, else the position."""
    if completed or position_ms < RESUME_MIN_MS:
        return 0
    if duration_ms is not None and duration_ms > 0 and position_ms >= duration_ms:
        return 0
    return position_ms


def _derive_completed(position_ms: int, duration_ms: int | None, explicit: bool | None) -> bool:
    if explicit is not None:
        return explicit
    if duration_ms is not None and duration_ms > 0:
        return position_ms >= int(duration_ms * COMPLETE_FRACTION)
    return False


def _view(entry: PlaybackEntry) -> PlaybackView:
    return PlaybackView(
        clip_id=entry.clip_id,
        position_ms=entry.position_ms,
        duration_ms=entry.duration_ms,
        completed=entry.completed,
        resume_position_ms=_resume_ms(entry.position_ms, entry.duration_ms, entry.completed),
        play_count=entry.play_count,
        updated_at=entry.updated_at,
    )


def get_playback(appstate: AppState, library_id: str, clip_id: str) -> PlaybackView | None:
    """Return stored playback for a clip, or ``None`` if it has never been played."""
    entry = appstate.get_playback(library_id, clip_id)
    return _view(entry) if entry is not None else None


def save_playback(
    appstate: AppState,
    library_id: str,
    clip_id: str,
    *,
    position_ms: int,
    duration_ms: int | None = None,
    completed: bool | None = None,
) -> PlaybackView:
    """Record the latest playback position, applying the completion policy, and return the view."""
    resolved = _derive_completed(position_ms, duration_ms, completed)
    entry = appstate.upsert_playback(
        library_id,
        clip_id,
        position_ms=position_ms,
        duration_ms=duration_ms,
        completed=resolved,
    )
    return _view(entry)
