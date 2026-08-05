from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from clipfetch.api.app import create_app  # noqa: E402
from clipfetch.appstate import AppState  # noqa: E402
from tests.webfixtures import build_fixture_library  # noqa: E402


def _client(tmp_path: Path) -> tuple[TestClient, Path]:
    library_dir = tmp_path / "reels"
    build_fixture_library(library_dir)
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    client = TestClient(create_app(appstate), raise_server_exceptions=False)
    created = client.post(
        "/api/v1/libraries", json={"display_name": "Reels", "path": str(library_dir)}
    )
    client.post(f"/api/v1/libraries/{created.json()['id']}/activate")
    return client, library_dir


def test_collection_exports_as_a_playlist_and_a_manifest(tmp_path):
    client, _ = _client(tmp_path)

    m3u = client.get("/api/v1/collections/popular/export?format=m3u")
    assert m3u.status_code == 200
    assert m3u.headers["content-type"].startswith("audio/x-mpegurl")
    assert 'filename="clipfetch-popular.m3u"' in m3u.headers["content-disposition"]
    assert m3u.text.startswith("#EXTM3U\n")

    manifest = client.get("/api/v1/collections/popular/export?format=json")
    assert manifest.status_code == 200
    body = json.loads(manifest.text)
    assert body["library"] == "."
    assert body["clips"] and all(clip["id"] for clip in body["clips"])
    assert manifest.headers["x-clip-count"] == str(len(body["clips"]))
    assert manifest.headers["x-export-truncated"] == "false"


def test_exports_never_carry_the_absolute_library_path(tmp_path):
    """The portability promise: an export must work after the library folder moves."""
    client, library_dir = _client(tmp_path)

    for path in (
        "/api/v1/collections/popular/export?format=m3u",
        "/api/v1/collections/popular/export?format=json",
        "/api/v1/clips/export?format=m3u",
        "/api/v1/clips/export?format=json",
    ):
        resp = client.get(path)
        assert resp.status_code == 200
        assert str(library_dir) not in resp.text
        assert str(tmp_path) not in resp.text


def test_a_hand_picked_clip_is_in_its_collection_export(tmp_path):
    client, _ = _client(tmp_path)
    client.post("/api/v1/collections", json={"name": "manual", "clips": ["IG_TRAVEL1"]})

    manifest = json.loads(client.get("/api/v1/collections/manual/export?format=json").text)
    assert [clip["id"] for clip in manifest["clips"]] == ["IG_TRAVEL1"]


def test_a_filtered_view_exports_exactly_what_it_shows(tmp_path):
    client, _ = _client(tmp_path)
    listed = client.get("/api/v1/clips?platform=tiktok&limit=100").json()
    shown = {item["id"] for item in listed["items"]}

    exported = json.loads(client.get("/api/v1/clips/export?format=json&platform=tiktok").text)
    assert {clip["id"] for clip in exported["clips"]} == shown
    assert shown  # the fixture has TikTok clips, so this is a real comparison


def test_export_names_the_file_from_the_view(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.get("/api/v1/clips/export?format=m3u&name=Top%20Picks!")
    # Whatever the caller sends becomes a safe filename.
    assert 'filename="clipfetch-top-picks.m3u"' in resp.headers["content-disposition"]


def test_export_route_is_not_swallowed_by_the_clip_id_route(tmp_path):
    """`/clips/export` must stay a route, not a clip called "export"."""
    client, _ = _client(tmp_path)
    resp = client.get("/api/v1/clips/export?format=m3u")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("audio/x-mpegurl")


def test_bad_format_and_unknown_collection_are_refused(tmp_path):
    client, _ = _client(tmp_path)
    assert client.get("/api/v1/clips/export?format=csv").status_code == 422
    assert client.get("/api/v1/collections/popular/export?format=csv").status_code == 422
    missing = client.get("/api/v1/collections/ghost/export?format=m3u")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "collection_not_found"


def test_export_requires_an_active_library(tmp_path):
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    client = TestClient(create_app(appstate), raise_server_exceptions=False)
    assert client.get("/api/v1/clips/export?format=m3u").status_code == 409
