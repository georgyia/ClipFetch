from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from clipfetch.api.app import create_app  # noqa: E402
from clipfetch.appstate import AppState  # noqa: E402
from tests.webfixtures import build_fixture_library  # noqa: E402


def _setup(tmp_path: Path):
    library_dir = tmp_path / "reels"
    build_fixture_library(library_dir)
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    client = TestClient(create_app(appstate), raise_server_exceptions=False)
    created = client.post(
        "/api/v1/libraries", json={"display_name": "Reels", "path": str(library_dir)}
    )
    library_id = created.json()["id"]
    client.post(f"/api/v1/libraries/{library_id}/activate")
    return client, appstate, library_id


def test_home_requires_active_library(tmp_path):
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    client = TestClient(create_app(appstate), raise_server_exceptions=False)
    assert client.get("/api/v1/home").status_code == 409


def test_home_rails_without_device_state(tmp_path):
    client, _appstate, _id = _setup(tmp_path)
    rails = client.get("/api/v1/home").json()["rails"]
    ids = [rail["id"] for rail in rails]

    assert ids[0] == "recent"  # no continue/favorites yet, so Recently Added leads
    assert "continue" not in ids and "favorites" not in ids
    # Topic rails are ordered by coverage (entertainment has 2 clips), then collections.
    assert "topic:entertainment" in ids
    assert "collection:popular" in ids and "collection:tech" in ids
    recent = next(rail for rail in rails if rail["id"] == "recent")
    assert len(recent["items"]) == 9


def test_home_includes_continue_and_favorites(tmp_path):
    client, appstate, library_id = _setup(tmp_path)
    appstate.add_favorite(library_id, "IG_COOK1")
    appstate.upsert_playback(library_id, "TT_FUN1", position_ms=5000, completed=False)
    appstate.upsert_playback(library_id, "IG_TRAVEL1", position_ms=22000, completed=True)

    rails = client.get("/api/v1/home").json()["rails"]
    ids = [rail["id"] for rail in rails]
    assert ids[0] == "continue"
    assert ids.index("continue") < ids.index("recent") < ids.index("favorites")

    cont = next(rail for rail in rails if rail["id"] == "continue")
    assert [item["id"] for item in cont["items"]] == ["TT_FUN1"]  # completed clip is excluded
    fav = next(rail for rail in rails if rail["id"] == "favorites")
    assert [item["id"] for item in fav["items"]] == ["IG_COOK1"]


def test_rail_pagination_and_unknown(tmp_path):
    client, appstate, library_id = _setup(tmp_path)
    appstate.add_favorite(library_id, "IG_TECH1")

    seen: list[str] = []
    cursor = None
    while True:
        params = {"limit": 4}
        if cursor:
            params["cursor"] = cursor
        page = client.get("/api/v1/rails/recent", params=params).json()
        seen.extend(item["id"] for item in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == 9

    topic = client.get("/api/v1/rails/topic:technology").json()
    assert [item["id"] for item in topic["items"]] == ["IG_TECH1"]

    fav = client.get("/api/v1/rails/favorites").json()
    assert [item["id"] for item in fav["items"]] == ["IG_TECH1"]

    assert client.get("/api/v1/rails/nope").status_code == 404
    assert client.get("/api/v1/rails/recent", params={"cursor": "!!bad!!"}).status_code == 422
