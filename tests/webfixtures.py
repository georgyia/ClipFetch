"""Deterministic, offline web fixture library for ClipFetch Watch tests.

:func:`build_fixture_library` materializes a complete ClipFetch library on disk — a versioned
catalog, media files, topics, manual topic assignments, and a saved collection — with the variety
the web layer must handle: multiple platforms, rich and partial metadata, a byte-identical duplicate
pair, and a clip whose media file is missing. It uses only the base install (no semantic/transcribe/
duplicate extras and no network), so it is safe to call from ordinary unit tests and future API/E2E
fixtures.

The output is intentionally stable: identical inputs produce an identical catalog and identical
media bytes, so tests can assert exact counts and ordering.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from clipfetch.catalog import Catalog, CatalogRecord
from clipfetch.collections import save_collection
from clipfetch.library import ClipFilter
from clipfetch.topics import init_topics

# Real, tiny, browser-decodable MP4s already vendored in the repo. Copied in for the clips that
# future playback/probe tests exercise; every other clip gets deterministic placeholder bytes.
_SAMPLE_MEDIA = Path(__file__).parent / "fixtures" / "visible_text"
_DUPLICATE_BYTES = b"clipfetch-fixture-duplicate-media\n" * 8


@dataclass(frozen=True)
class _Seed:
    platform: str
    clip_id: str
    author: str | None
    caption: str | None
    likes: int | None
    views: int | None
    duration_seconds: float | None
    hashtags: tuple[str, ...]
    downloaded_at: str
    metadata_state: str
    available: bool = True
    topic: str | None = None
    sample_media: str | None = None
    duplicate: bool = False


@dataclass(frozen=True)
class FixtureSummary:
    """What :func:`build_fixture_library` created, for assertions and diagnostics."""

    root: Path
    total_clips: int
    available_clips: int
    unavailable_clips: int
    platforms: tuple[str, ...]
    topics: tuple[str, ...]
    manual_topic_assignments: int
    collections: tuple[str, ...]
    duplicate_group_size: int


_SEEDS: tuple[_Seed, ...] = (
    _Seed("instagram", "IG_COOK1", "chefana", "Easy weeknight pasta #food #recipe",
          1_500_000, 9_000_000, 31.0, ("food", "recipe"), "2026-06-01T09:00:00+00:00",
          "sidecar-v2", topic="food", sample_media="static_title.mp4"),
    _Seed("instagram", "IG_TECH1", "devlog", "Ship faster with this trick #tech",
          2_200_000, 12_000_000, 45.0, ("tech",), "2026-06-02T09:00:00+00:00",
          "sidecar-v2", topic="technology", sample_media="no_text.mp4"),
    _Seed("instagram", "IG_TRAVEL1", "wander", "Kyoto in the fall is unreal",
          800_000, 3_000_000, 22.0, (), "2026-06-03T09:00:00+00:00", "sidecar-v2"),
    _Seed("tiktok", "TT_FUN1", "jokes", "wait for it #comedy",
          5_000_000, 40_000_000, 15.0, ("comedy",), "2026-06-04T09:00:00+00:00",
          "sidecar-v2", topic="entertainment"),
    _Seed("tiktok", "TT_FIT1", "coach", "10 minute core, no equipment",
          400_000, 1_200_000, 58.0, ("fitness",), "2026-06-05T09:00:00+00:00",
          "sidecar-v2", topic="health-and-fitness"),
    _Seed("instagram", "IG_PARTIAL", None, None,
          None, None, None, (), "2026-06-06T09:00:00+00:00", "legacy-sidecar"),
    _Seed("instagram", "IG_DUP_A", "repost", "same clip, first copy",
          120_000, 500_000, 20.0, (), "2026-06-07T09:00:00+00:00", "sidecar-v2", duplicate=True),
    _Seed("instagram", "IG_DUP_B", "mirror", "same clip, reposted",
          90_000, 400_000, 20.0, (), "2026-06-08T09:00:00+00:00", "sidecar-v2", duplicate=True),
    _Seed("tiktok", "TT_MUSIC1", "dj", "new beat dropping #music",
          700_000, 2_500_000, 40.0, ("music",), "2026-06-09T09:00:00+00:00",
          "sidecar-v2", topic="entertainment"),
    _Seed("instagram", "IG_GONE", "ghost", "media deleted from disk",
          10_000, 50_000, 18.0, (), "2026-06-10T09:00:00+00:00", "sidecar-v2", available=False),
)


def _record(seed: _Seed) -> CatalogRecord:
    return CatalogRecord(
        platform=seed.platform,
        clip_id=seed.clip_id,
        relative_path=f"{seed.platform}/{seed.clip_id}.mp4",
        file_size=len(_DUPLICATE_BYTES) if seed.duplicate else max(len(seed.clip_id), 1),
        file_mtime_ns=1_700_000_000_000_000_000,
        downloaded_at=seed.downloaded_at,
        source_url=f"https://example.invalid/{seed.platform}/{seed.clip_id}",
        author=seed.author,
        caption=seed.caption,
        likes=seed.likes,
        metadata_state=seed.metadata_state,
        available=seed.available,
        hashtags=seed.hashtags,
        views=seed.views,
        duration_seconds=seed.duration_seconds,
    )


def _media_bytes(seed: _Seed) -> bytes:
    if seed.duplicate:
        return _DUPLICATE_BYTES
    return f"clipfetch-fixture:{seed.platform}:{seed.clip_id}\n".encode()


def build_fixture_library(root: Path) -> FixtureSummary:
    """Create a complete, deterministic fixture library under ``root`` and return its summary."""
    root.mkdir(parents=True, exist_ok=True)

    with Catalog.open(root) as catalog:
        for seed in _SEEDS:
            catalog.upsert(_record(seed))
            if not seed.available:
                continue
            media_path = root / f"{seed.platform}/{seed.clip_id}.mp4"
            media_path.parent.mkdir(parents=True, exist_ok=True)
            sample = _SAMPLE_MEDIA / seed.sample_media if seed.sample_media else None
            if sample is not None and sample.is_file():
                shutil.copyfile(sample, media_path)
            else:
                media_path.write_bytes(_media_bytes(seed))

    init_topics(root)
    manual_assignments = 0
    with Catalog.open(root) as catalog:
        for seed in _SEEDS:
            if seed.topic:
                catalog.set_manual_topic(seed.platform, seed.clip_id, seed.topic)
                manual_assignments += 1

    save_collection(root, "popular", ClipFilter(min_likes=1_000_000))
    save_collection(root, "tech", ClipFilter(topics=("technology",)))

    available = [seed for seed in _SEEDS if seed.available]
    unavailable = [seed for seed in _SEEDS if not seed.available]
    return FixtureSummary(
        root=root,
        total_clips=len(_SEEDS),
        available_clips=len(available),
        unavailable_clips=len(unavailable),
        platforms=tuple(sorted({seed.platform for seed in _SEEDS})),
        topics=tuple(sorted({seed.topic for seed in _SEEDS if seed.topic})),
        manual_topic_assignments=manual_assignments,
        collections=("popular", "tech"),
        duplicate_group_size=sum(1 for seed in _SEEDS if seed.duplicate),
    )
