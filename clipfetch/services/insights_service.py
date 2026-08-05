"""Library insights: what is in this library, and what actually got watched.

Every figure here is computed on demand from data the app already keeps — the device-local
playback rows and the library's own catalog. Nothing new is recorded, nothing is written when the
view is opened, and nothing leaves the machine. That is the point: it is the honest counterweight
to an engagement feed, showing your own consumption back to you rather than optimizing it.

Two definitions worth stating, because a statistic nobody can interpret is decoration:

* **Watch time** is the furthest point reached in each clip, summed — a finished clip counts its
  duration once, an abandoned one counts where it stopped. Rewatches are *not* multiplied in:
  nothing records whether a second play ran to the end, so that number would be invented.
* **Plays** is the running total of starts, which is why it can exceed the number of clips watched.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clipfetch.appstate import AppState
from clipfetch.catalog import Catalog

#: How many creators/topics a leaderboard returns. Long enough to be interesting, short enough to
#: read; the underlying views are one click away for everything else.
TOP_N = 8
#: Days of activity history reported.
ACTIVITY_DAYS = 30


@dataclass(frozen=True)
class Insights:
    totals: dict[str, Any]
    top_creators: tuple[dict[str, Any], ...]
    top_topics: tuple[dict[str, Any], ...]
    activity: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "totals": self.totals,
            "top_creators": list(self.top_creators),
            "top_topics": list(self.top_topics),
            "activity": list(self.activity),
        }


def library_insights(root: Path, appstate: AppState, library_id: str) -> Insights:
    """Summarize one library's contents and how much of it has actually been watched."""
    totals = appstate.playback_totals(library_id)
    playback = {entry.clip_id: entry for entry in appstate.all_playback(library_id)}

    # One pass over the catalog, shared by every metric below, rather than a query per figure.
    with Catalog.open(root) as catalog:
        records = list(catalog.all())
        assigned_topics = catalog.all_topic_names()

    creator_plays: dict[str, int] = defaultdict(int)
    creator_clips: dict[str, int] = defaultdict(int)
    topic_plays: dict[str, int] = defaultdict(int)
    topic_clips: dict[str, int] = defaultdict(int)
    watched_ids: set[str] = set()

    for record in records:
        entry = playback.get(record.clip_id)
        plays = entry.play_count if entry else 0
        if entry is not None:
            watched_ids.add(record.clip_id)
        if record.author:
            creator_clips[record.author] += 1
            creator_plays[record.author] += plays
        for topic in assigned_topics.get((record.platform, record.clip_id), ()):
            topic_clips[topic] += 1
            topic_plays[topic] += plays

    # Playback rows can outlive their clips (a forgotten record, a library re-pointed), so the
    # watched count is the intersection with what the catalog still holds, not the row count.
    watched = len(watched_ids)
    return Insights(
        totals={
            "clips": len(records),
            "watched_clips": watched,
            "unwatched_clips": max(0, len(records) - watched),
            "completed_clips": totals["completed"],
            "plays": totals["plays"],
            "watch_time_seconds": totals["watched_ms"] // 1000,
        },
        top_creators=_leaderboard(creator_plays, creator_clips, "creator"),
        top_topics=_leaderboard(topic_plays, topic_clips, "topic"),
        activity=tuple(
            {"day": day, "clips": clips}
            for day, clips in appstate.plays_by_day(library_id, days=ACTIVITY_DAYS)
        ),
    )


def _leaderboard(
    plays: dict[str, int], clips: dict[str, int], key: str
) -> tuple[dict[str, Any], ...]:
    """Rank by plays, then by how much of it you own, then by name so ties are stable."""
    ranked = sorted(
        plays.items(), key=lambda item: (-item[1], -clips.get(item[0], 0), item[0].casefold())
    )
    return tuple(
        {key: name, "plays": count, "clips": clips.get(name, 0)}
        for name, count in ranked[:TOP_N]
        if count > 0 or clips.get(name, 0) > 0
    )
