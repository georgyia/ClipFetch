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
    assert client.post("/api/v1/collections/x/clips", json={"clip_ids": ["A"]}).status_code == 409


def _ids(client, collection_id: str) -> list[str]:
    page = client.get(f"/api/v1/collections/{collection_id}/clips?limit=100").json()
    return [item["id"] for item in page["items"]]


def test_pinning_a_clip_adds_it_regardless_of_the_filter(tmp_path):
    client = _client(tmp_path)
    created = client.post(
        "/api/v1/collections", json={"name": "big-hits", "filters": {"min_likes": 1000000}}
    ).json()
    assert created["pinned"] == [] and created["pinned_count"] == 0
    matched = _ids(client, "big-hits")
    assert "IG_TRAVEL1" not in matched  # 800k likes: below the filter.

    pinned = client.post("/api/v1/collections/big-hits/clips", json={"clip_ids": ["IG_TRAVEL1"]})
    assert pinned.status_code == 200
    assert pinned.json()["pinned"] == ["IG_TRAVEL1"]
    assert pinned.json()["clip_count"] == created["clip_count"] + 1
    assert set(_ids(client, "big-hits")) == {*matched, "IG_TRAVEL1"}

    # Pinning something the filter already matches does not double-count it.
    again = client.post("/api/v1/collections/big-hits/clips", json={"clip_ids": [matched[0]]})
    assert again.json()["clip_count"] == created["clip_count"] + 1

    removed = client.delete("/api/v1/collections/big-hits/clips/IG_TRAVEL1")
    assert removed.status_code == 200 and removed.json()["pinned"] == [matched[0]]
    assert "IG_TRAVEL1" not in _ids(client, "big-hits")


def test_collection_without_filters_contains_only_pinned_clips(tmp_path):
    client = _client(tmp_path)
    manual = client.post("/api/v1/collections", json={"name": "manual"})
    assert manual.status_code == 201
    assert manual.json()["filters"] is None and manual.json()["clip_count"] == 0

    client.post("/api/v1/collections/manual/clips", json={"clip_ids": ["IG_COOK1", "TT_FUN1"]})
    assert set(_ids(client, "manual")) == {"IG_COOK1", "TT_FUN1"}

    # An explicit empty filter is a different thing: it matches the whole library.
    everything = client.post("/api/v1/collections", json={"name": "everything", "filters": {}})
    assert everything.json()["clip_count"] > 2

    # Dropping the filter of an existing collection keeps its pins.
    client.post("/api/v1/collections/everything/clips", json={"clip_ids": ["IG_COOK1"]})
    dropped = client.put("/api/v1/collections/everything", json={"filters": None})
    assert dropped.json()["filters"] is None
    assert dropped.json()["pinned"] == ["IG_COOK1"] and dropped.json()["clip_count"] == 1


def test_creating_a_collection_can_pin_clips_in_one_call(tmp_path):
    client = _client(tmp_path)
    created = client.post(
        "/api/v1/collections", json={"name": "starter", "clips": ["IG_COOK1", "IG_COOK1"]}
    )
    assert created.status_code == 201 and created.json()["pinned"] == ["IG_COOK1"]


def test_pinning_rejects_unknown_clips_and_collections(tmp_path):
    client = _client(tmp_path)
    client.post("/api/v1/collections", json={"name": "manual"})

    unknown_clip = client.post("/api/v1/collections/manual/clips", json={"clip_ids": ["nope"]})
    assert unknown_clip.status_code == 404
    assert unknown_clip.json()["error"]["code"] == "clip_not_found"
    # A rejected batch writes nothing.
    assert client.get("/api/v1/collections/manual").json()["pinned"] == []

    unknown_collection = client.post(
        "/api/v1/collections/ghost/clips", json={"clip_ids": ["IG_COOK1"]}
    )
    assert unknown_collection.status_code == 404
    assert unknown_collection.json()["error"]["code"] == "collection_not_found"
    assert client.delete("/api/v1/collections/ghost/clips/IG_COOK1").status_code == 404
    assert client.post("/api/v1/collections/manual/clips", json={"clip_ids": []}).status_code == 422


def test_unpinning_a_clip_that_left_the_library_still_works(tmp_path):
    client = _client(tmp_path)
    client.post("/api/v1/collections", json={"name": "manual", "clips": ["IG_COOK1"]})
    # The catalog check is deliberately not applied to removal, so a stale pin can be cleaned up.
    assert client.delete("/api/v1/collections/manual/clips/IG_COOK1").json()["pinned"] == []
    assert client.delete("/api/v1/collections/manual/clips/never-existed").status_code == 200
