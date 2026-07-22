from __future__ import annotations

from pathlib import Path

from clipfetch.collections import load_collections, resolve_collection
from clipfetch.library import ClipFilter, query_library
from clipfetch.topics import load_topics
from tests.webfixtures import build_fixture_library


def test_summary_counts_match_catalog(tmp_path: Path):
    summary = build_fixture_library(tmp_path)

    assert summary.total_clips == 10
    assert summary.available_clips == 9
    assert summary.unavailable_clips == 1
    assert summary.platforms == ("instagram", "tiktok")
    assert summary.duplicate_group_size == 2

    result = query_library(tmp_path)
    # The unavailable clip is excluded because its media file is missing.
    assert result.matched == summary.available_clips
    assert result.excluded == summary.unavailable_clips


def test_topics_and_manual_assignments_present(tmp_path: Path):
    summary = build_fixture_library(tmp_path)

    config = load_topics(tmp_path)
    starter = {topic.name for topic in config.topics}
    assert {"food", "technology", "health-and-fitness", "entertainment"} <= starter

    # Manual topic assignments make topic filters return real rows.
    tech = query_library(tmp_path, ClipFilter(topics=("technology",)))
    assert [record.clip_id for record in tech.clips] == ["IG_TECH1"]
    assert summary.manual_topic_assignments == 5


def test_saved_collections_resolve(tmp_path: Path):
    build_fixture_library(tmp_path)

    names = {item.name for item in load_collections(tmp_path)}
    assert names == {"popular", "tech"}

    popular = resolve_collection(tmp_path, "popular")
    assert {record.clip_id for record in popular.clips} == {"IG_COOK1", "IG_TECH1", "TT_FUN1"}


def test_duplicate_pair_is_byte_identical(tmp_path: Path):
    build_fixture_library(tmp_path)

    dup_a = (tmp_path / "instagram" / "IG_DUP_A.mp4").read_bytes()
    dup_b = (tmp_path / "instagram" / "IG_DUP_B.mp4").read_bytes()
    assert dup_a == dup_b and len(dup_a) > 0


def test_generation_is_deterministic_and_offline(tmp_path: Path):
    first = build_fixture_library(tmp_path / "a")
    second = build_fixture_library(tmp_path / "b")

    def media_map(root: Path) -> dict[str, bytes]:
        return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*.mp4"))}

    assert first.total_clips == second.total_clips
    assert media_map(tmp_path / "a") == media_map(tmp_path / "b")
