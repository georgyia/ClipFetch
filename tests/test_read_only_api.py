from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from clipfetch.api.app import create_app  # noqa: E402
from clipfetch.appstate import AppState  # noqa: E402
from tests.webfixtures import build_fixture_library  # noqa: E402


def _bare_client(tmp_path: Path) -> TestClient:
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    return TestClient(create_app(appstate), raise_server_exceptions=False)


def _client_with_library(tmp_path: Path) -> TestClient:
    library_dir = tmp_path / "reels"
    build_fixture_library(library_dir)
    client = _bare_client(tmp_path)
    created = client.post(
        "/api/v1/libraries", json={"display_name": "Reels", "path": str(library_dir)}
    )
    client.post(f"/api/v1/libraries/{created.json()['id']}/activate")
    return client


def test_requires_active_library(tmp_path):
    resp = _bare_client(tmp_path).get("/api/v1/clips")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "no_active_library"


def test_clip_listing_paginates_over_available_clips(tmp_path):
    client = _client_with_library(tmp_path)
    ids: list[str] = []
    cursor = None
    pages = 0
    while True:
        params = {"limit": 4}
        if cursor:
            params["cursor"] = cursor
        body = client.get("/api/v1/clips", params=params).json()
        assert body["total_matched"] == 9  # 9 available; the missing-media clip is excluded
        ids.extend(item["id"] for item in body["items"])
        pages += 1
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert pages == 3
    assert len(ids) == len(set(ids)) == 9


def test_clip_filters_map_to_clipfilter(tmp_path):
    client = _client_with_library(tmp_path)
    popular = client.get("/api/v1/clips", params={"min_likes": 1_000_000, "sort": "likes"}).json()
    assert [item["id"] for item in popular["items"]] == ["TT_FUN1", "IG_TECH1", "IG_COOK1"]

    by_topic = client.get("/api/v1/clips", params={"topic": "technology"}).json()
    assert [item["id"] for item in by_topic["items"]] == ["IG_TECH1"]

    by_creator = client.get("/api/v1/clips", params={"creator": "chefana"}).json()
    assert [item["id"] for item in by_creator["items"]] == ["IG_COOK1"]


def test_invalid_sort_and_cursor_are_422(tmp_path):
    client = _client_with_library(tmp_path)
    assert client.get("/api/v1/clips", params={"sort": "bogus"}).json()["error"]["code"] == (
        "invalid_sort"
    )
    bad = client.get("/api/v1/clips", params={"cursor": "!!not-valid!!"})
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "invalid_cursor"


def test_clip_detail_and_missing(tmp_path):
    client = _client_with_library(tmp_path)
    detail = client.get("/api/v1/clips/IG_COOK1")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == "IG_COOK1"
    assert body["topics"] == ["food"]
    assert "relative_path" not in detail.text
    assert str(tmp_path) not in detail.text

    missing = client.get("/api/v1/clips/DOES_NOT_EXIST")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "clip_not_found"


def test_topic_endpoints(tmp_path):
    client = _client_with_library(tmp_path)
    topics = {t["slug"]: t for t in client.get("/api/v1/topics").json()["topics"]}
    assert topics["technology"]["clip_count"] == 1

    assert client.get("/api/v1/topics/technology").json()["clip_count"] == 1
    clips = client.get("/api/v1/topics/technology/clips").json()
    assert [item["id"] for item in clips["items"]] == ["IG_TECH1"]

    assert client.get("/api/v1/topics/nope").status_code == 404
    assert client.get("/api/v1/topics/nope/clips").status_code == 404


def test_collection_endpoints(tmp_path):
    client = _client_with_library(tmp_path)
    names = {c["id"]: c for c in client.get("/api/v1/collections").json()["collections"]}
    assert set(names) == {"popular", "tech"}
    assert names["popular"]["clip_count"] == 3

    clips = client.get("/api/v1/collections/popular/clips", params={"sort": "likes"}).json()
    assert [item["id"] for item in clips["items"]] == ["TT_FUN1", "IG_TECH1", "IG_COOK1"]

    assert client.get("/api/v1/collections/nope").status_code == 404
    assert client.get("/api/v1/collections/nope/clips").status_code == 404
