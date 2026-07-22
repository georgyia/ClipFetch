from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from clipfetch.api.app import create_app  # noqa: E402
from clipfetch.appstate import AppState  # noqa: E402
from tests.webfixtures import build_fixture_library  # noqa: E402


def _client(tmp_path: Path):
    library_dir = tmp_path / "reels"
    build_fixture_library(library_dir)
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    client = TestClient(create_app(appstate), raise_server_exceptions=False)
    created = client.post(
        "/api/v1/libraries", json={"display_name": "Reels", "path": str(library_dir)}
    )
    client.post(f"/api/v1/libraries/{created.json()['id']}/activate")
    return client


def test_favorite_toggle_and_list(tmp_path):
    client = _client(tmp_path)

    assert client.get("/api/v1/clips/IG_COOK1/favorite").json()["favorite"] is False
    assert client.get("/api/v1/favorites").json()["items"] == []

    added = client.put("/api/v1/clips/IG_COOK1/favorite")
    assert added.status_code == 200
    assert added.json()["favorite"] is True
    assert client.get("/api/v1/clips/IG_COOK1/favorite").json()["favorite"] is True

    listed = client.get("/api/v1/favorites").json()
    assert [item["id"] for item in listed["items"]] == ["IG_COOK1"]

    removed = client.delete("/api/v1/clips/IG_COOK1/favorite")
    assert removed.status_code == 204
    assert client.get("/api/v1/favorites").json()["items"] == []


def test_favorite_is_idempotent(tmp_path):
    client = _client(tmp_path)
    client.put("/api/v1/clips/IG_COOK1/favorite")
    client.put("/api/v1/clips/IG_COOK1/favorite")
    assert len(client.get("/api/v1/favorites").json()["items"]) == 1


def test_favorites_require_active_library(tmp_path):
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    client = TestClient(create_app(appstate), raise_server_exceptions=False)
    assert client.get("/api/v1/favorites").status_code == 409
    assert client.put("/api/v1/clips/IG_COOK1/favorite").status_code == 409
