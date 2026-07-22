from __future__ import annotations

from pathlib import Path

import pytest

from clipfetch.appstate import CURRENT_SCHEMA_VERSION, AppState, AppStateError


def _open(tmp_path: Path) -> AppState:
    return AppState.open(tmp_path / "appstate.sqlite3")


def test_migrations_apply_and_reopen_is_idempotent(tmp_path):
    with _open(tmp_path) as state:
        assert state.schema_version == CURRENT_SCHEMA_VERSION
    # Reopening the same file must not re-run migrations or error.
    with _open(tmp_path) as state:
        assert state.schema_version == CURRENT_SCHEMA_VERSION


def test_library_registry_is_idempotent_by_path(tmp_path):
    with _open(tmp_path) as state:
        first = state.register_library("Reels", tmp_path / "reels")
        again = state.register_library("Reels renamed", tmp_path / "reels")
        assert first.id == again.id  # same path -> same registration
        assert len(state.list_libraries()) == 1

        other = state.register_library("Clips", tmp_path / "clips")
        assert {lib.id for lib in state.list_libraries()} == {first.id, other.id}

        with pytest.raises(AppStateError, match="unknown library"):
            state.get_library("nope")


def test_activate_sets_last_opened(tmp_path):
    with _open(tmp_path) as state:
        a = state.register_library("A", tmp_path / "a")
        b = state.register_library("B", tmp_path / "b")
        assert state.last_opened_library() is None

        state.activate_library(a.id)
        state.activate_library(b.id)
        assert state.last_opened_library().id == b.id
        assert state.get_library(a.id).last_opened_at is not None


def test_unregister_removes_state_but_leaves_files(tmp_path):
    library_dir = tmp_path / "reels"
    library_dir.mkdir()
    (library_dir / "keep.mp4").write_bytes(b"video")
    with _open(tmp_path) as state:
        entry = state.register_library("Reels", library_dir)
        state.add_favorite(entry.id, "CLIP01")
        other = state.register_library("Other", tmp_path / "other")
        state.add_favorite(other.id, "CLIP99")

        state.unregister_library(entry.id)
        assert [lib.id for lib in state.list_libraries()] == [other.id]
        assert state.list_favorites(entry.id) == ()
        assert state.list_favorites(other.id) == ("CLIP99",)  # untouched
        with pytest.raises(AppStateError, match="unknown library"):
            state.unregister_library(entry.id)

    # The library's files are never touched by unregistering.
    assert (library_dir / "keep.mp4").is_file()


def test_playback_upsert_counts_and_coalesces_duration(tmp_path):
    with _open(tmp_path) as state:
        lib = state.register_library("L", tmp_path / "l")
        first = state.upsert_playback(lib.id, "CLIP01", position_ms=1000, duration_ms=30000)
        assert first.position_ms == 1000 and first.play_count == 1 and first.completed is False

        second = state.upsert_playback(lib.id, "CLIP01", position_ms=29000, completed=True)
        assert second.position_ms == 29000
        assert second.play_count == 2
        assert second.completed is True
        assert second.duration_ms == 30000  # preserved when the update omits it

        with pytest.raises(AppStateError, match="non-negative"):
            state.upsert_playback(lib.id, "CLIP01", position_ms=-1)


def test_recent_playback_is_newest_first(tmp_path):
    with _open(tmp_path) as state:
        lib = state.register_library("L", tmp_path / "l")
        state.upsert_playback(lib.id, "OLD", position_ms=1)
        state.upsert_playback(lib.id, "NEW", position_ms=1)
        recent = state.recent_playback(lib.id, limit=10)
        assert [entry.clip_id for entry in recent][0] == "NEW"


def test_favorites_add_remove_and_idempotent(tmp_path):
    with _open(tmp_path) as state:
        lib = state.register_library("L", tmp_path / "l")
        state.add_favorite(lib.id, "CLIP01")
        state.add_favorite(lib.id, "CLIP01")  # idempotent
        assert state.is_favorite(lib.id, "CLIP01") is True
        assert state.list_favorites(lib.id) == ("CLIP01",)

        state.remove_favorite(lib.id, "CLIP01")
        assert state.is_favorite(lib.id, "CLIP01") is False
        assert state.list_favorites(lib.id) == ()
