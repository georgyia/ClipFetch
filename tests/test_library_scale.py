from __future__ import annotations

from pathlib import Path

from clipfetch.catalog import Catalog, CatalogRecord
from clipfetch.library import ClipFilter, query_library
from clipfetch.services import catalog_service


def _build_library(root: Path, count: int) -> None:
    """Materialize a library of ``count`` clips with media, cheaply (no browser, no network)."""
    root.mkdir(parents=True, exist_ok=True)
    with Catalog.open(root) as catalog:
        for index in range(count):
            clip_id = f"C{index:05d}"
            catalog.upsert(
                CatalogRecord(
                    platform="instagram",
                    clip_id=clip_id,
                    relative_path=f"instagram/{clip_id}.mp4",
                    file_size=10,
                    file_mtime_ns=1,
                    downloaded_at=f"2026-01-01T00:{index % 60:02d}:00+00:00",
                    source_url=None,
                    author=f"creator_{index % 50}",
                    caption=f"clip {index}",
                    likes=index,
                    metadata_state="complete",
                    available=True,
                    hashtags=(),
                    views=index * 10,
                )
            )
            media = root / "instagram" / f"{clip_id}.mp4"
            media.parent.mkdir(parents=True, exist_ok=True)
            media.write_bytes(b"x")


def test_page_is_bounded_and_paginates_whole_library(tmp_path):
    root = tmp_path / "lib"
    _build_library(root, 1500)

    seen: set[str] = set()
    cursor: str | None = None
    pages = 0
    while True:
        page = catalog_service.list_clips(root, sort="date", cursor=cursor, limit=100)
        assert len(page.items) <= 100  # every page is bounded regardless of library size
        for item in page.items:
            assert item.id not in seen  # no duplicates across pages
            seen.add(item.id)
        pages += 1
        if page.next_cursor is None:
            break
        cursor = page.next_cursor
        assert pages < 100  # guards against a pagination loop

    assert len(seen) == 1500
    assert page.total_matched == 1500


def test_batched_topic_names_matches_per_clip(tmp_path):
    root = tmp_path / "lib"
    _build_library(root, 20)
    with Catalog.open(root) as catalog:
        catalog.set_manual_topic("instagram", "C00003", "cooking")
        catalog.set_manual_topic("instagram", "C00007", "fitness")
        batch = catalog.all_topic_names()
        assert batch[("instagram", "C00003")] == ("cooking",)
        assert batch[("instagram", "C00007")] == ("fitness",)
        # Clips with no topics are simply absent from the batch.
        assert ("instagram", "C00001") not in batch


def test_topic_filter_still_correct_at_scale(tmp_path):
    root = tmp_path / "lib"
    _build_library(root, 300)
    with Catalog.open(root) as catalog:
        for clip_id in ("C00010", "C00020", "C00030"):
            catalog.set_manual_topic("instagram", clip_id, "cooking")
    result = query_library(root, ClipFilter(topics=("cooking",)))
    assert result.matched == 3
