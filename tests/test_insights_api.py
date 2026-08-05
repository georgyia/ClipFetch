from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from clipfetch.api.app import create_app  # noqa: E402
from clipfetch.appstate import AppState  # noqa: E402
from tests.webfixtures import build_fixture_library  # noqa: E402


def _client(tmp_path: Path) -> tuple[TestClient, AppState, str]:
    library_dir = tmp_path / "reels"
    build_fixture_library(library_dir)
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    client = TestClient(create_app(appstate), raise_server_exceptions=False)
    created = client.post(
        "/api/v1/libraries", json={"display_name": "Reels", "path": str(library_dir)}
    ).json()
    client.post(f"/api/v1/libraries/{created['id']}/activate")
    return client, appstate, created["id"]


def test_a_library_nobody_has_watched_reads_as_zero_not_as_broken(tmp_path):
    client, _, _ = _client(tmp_path)
    body = client.get("/api/v1/insights").json()

    assert body["totals"]["clips"] > 0
    assert body["totals"]["watched_clips"] == 0
    assert body["totals"]["unwatched_clips"] == body["totals"]["clips"]
    assert body["totals"]["watch_time_seconds"] == 0
    assert body["activity"] == []
    # Creators are still ranked: you own clips by them even if you have not played any.
    assert body["top_creators"]


def test_watch_time_counts_the_furthest_point_reached_once(tmp_path):
    client, appstate, library_id = _client(tmp_path)

    # One finished clip (30s) and one abandoned 10s into a 60s clip.
    appstate.upsert_playback(
        library_id, "IG_COOK1", position_ms=30_000, duration_ms=30_000, completed=True
    )
    appstate.upsert_playback(
        library_id, "IG_TECH1", position_ms=10_000, duration_ms=60_000, completed=False
    )
    totals = client.get("/api/v1/insights").json()["totals"]

    assert totals["watch_time_seconds"] == 40
    assert totals["watched_clips"] == 2 and totals["completed_clips"] == 1
    assert totals["unwatched_clips"] == totals["clips"] - 2


def test_a_rewatch_counts_as_a_play_but_not_as_more_watch_time(tmp_path):
    """Nothing records whether a second play ran to the end, so multiplying would be invented."""
    client, appstate, library_id = _client(tmp_path)
    for _ in range(3):
        appstate.upsert_playback(
            library_id, "IG_COOK1", position_ms=30_000, duration_ms=30_000, completed=True
        )

    totals = client.get("/api/v1/insights").json()["totals"]
    assert totals["plays"] == 3
    assert totals["watched_clips"] == 1
    assert totals["watch_time_seconds"] == 30


def test_creators_and_topics_are_ranked_by_plays(tmp_path):
    client, appstate, library_id = _client(tmp_path)
    for _ in range(2):
        appstate.upsert_playback(library_id, "TT_FUN1", position_ms=15_000, duration_ms=15_000)
    appstate.upsert_playback(library_id, "IG_COOK1", position_ms=5_000, duration_ms=31_000)

    body = client.get("/api/v1/insights").json()
    assert body["top_creators"][0] == {"creator": "jokes", "plays": 2, "clips": 1}
    top_topic = body["top_topics"][0]
    assert top_topic["topic"] == "entertainment" and top_topic["plays"] == 2


def test_activity_reports_clips_touched_per_day(tmp_path):
    client, appstate, library_id = _client(tmp_path)
    appstate.upsert_playback(library_id, "IG_COOK1", position_ms=1_000)
    appstate.upsert_playback(library_id, "IG_TECH1", position_ms=1_000)

    activity = client.get("/api/v1/insights").json()["activity"]
    assert len(activity) == 1
    assert activity[0]["clips"] == 2
    assert len(activity[0]["day"]) == 10  # YYYY-MM-DD


def test_playback_for_a_clip_the_catalog_no_longer_has_is_not_counted(tmp_path):
    """Rows outlive clips — a forgotten record, a re-pointed library — so they must not inflate."""
    client, appstate, library_id = _client(tmp_path)
    appstate.upsert_playback(library_id, "GHOST_CLIP", position_ms=99_000, duration_ms=99_000)

    totals = client.get("/api/v1/insights").json()["totals"]
    assert totals["watched_clips"] == 0
    assert totals["unwatched_clips"] == totals["clips"]


def test_insights_are_scoped_to_the_active_library(tmp_path):
    client, appstate, _ = _client(tmp_path)
    appstate.upsert_playback("some-other-library", "IG_COOK1", position_ms=30_000)

    assert client.get("/api/v1/insights").json()["totals"]["watched_clips"] == 0


def test_insights_need_an_active_library(tmp_path):
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    client = TestClient(create_app(appstate), raise_server_exceptions=False)
    assert client.get("/api/v1/insights").status_code == 409


def test_the_response_never_carries_a_device_path(tmp_path):
    client, _, _ = _client(tmp_path)
    resp = client.get("/api/v1/insights")
    assert str(tmp_path) not in resp.text
