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


def test_create_update_delete_collection(tmp_path):
    client = _client(tmp_path)

    created = client.post(
        "/api/v1/collections",
        json={"name": "big-hits", "filters": {"min_likes": 1000}},
    )
    assert created.status_code == 201
    collection_id = created.json()["id"]
    assert created.json()["filters"]["min_likes"] == 1000

    listed = client.get("/api/v1/collections").json()["collections"]
    assert any(item["id"] == collection_id for item in listed)

    updated = client.put(
        f"/api/v1/collections/{collection_id}",
        json={"filters": {"min_likes": 500000}},
    )
    assert updated.status_code == 200
    assert updated.json()["filters"]["min_likes"] == 500000

    # The collection browses its matching clips.
    clips = client.get(f"/api/v1/collections/{collection_id}/clips")
    assert clips.status_code == 200

    removed = client.delete(f"/api/v1/collections/{collection_id}")
    assert removed.status_code == 204
    remaining = client.get("/api/v1/collections").json()["collections"]
    assert all(item["id"] != collection_id for item in remaining)


def test_duplicate_name_is_rejected(tmp_path):
    client = _client(tmp_path)
    client.post("/api/v1/collections", json={"name": "dupe", "filters": {}})
    again = client.post("/api/v1/collections", json={"name": "dupe", "filters": {}})
    assert again.status_code == 422


def test_update_missing_collection_is_404(tmp_path):
    client = _client(tmp_path)
    resp = client.put("/api/v1/collections/ghost", json={"filters": {"min_likes": 1}})
    assert resp.status_code == 404


def test_mutations_require_active_library(tmp_path):
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    client = TestClient(create_app(appstate), raise_server_exceptions=False)
    assert client.post("/api/v1/collections", json={"name": "x", "filters": {}}).status_code == 409
