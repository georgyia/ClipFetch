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
    client.post(f"/api/v1/libraries/{created.json()['id']}/activate")
    return client, library_dir


def test_full_get_streams_whole_file(tmp_path):
    client, library_dir = _setup(tmp_path)
    raw = (library_dir / "instagram" / "IG_COOK1.mp4").read_bytes()

    resp = client.get("/api/v1/clips/IG_COOK1/media")
    assert resp.status_code == 200
    assert resp.headers["accept-ranges"] == "bytes"
    assert resp.headers["content-type"].startswith("video/mp4")
    assert resp.headers["content-length"] == str(len(raw))
    assert resp.content == raw
    assert resp.headers["etag"]


def test_head_returns_metadata_without_body(tmp_path):
    client, library_dir = _setup(tmp_path)
    size = len((library_dir / "instagram" / "IG_COOK1.mp4").read_bytes())
    resp = client.head("/api/v1/clips/IG_COOK1/media")
    assert resp.status_code == 200
    assert resp.headers["content-length"] == str(size)
    assert resp.headers["accept-ranges"] == "bytes"
    assert resp.content == b""


def test_ranges_return_206_with_correct_slices(tmp_path):
    client, library_dir = _setup(tmp_path)
    raw = (library_dir / "instagram" / "IG_COOK1.mp4").read_bytes()
    size = len(raw)

    prefix = client.get("/api/v1/clips/IG_COOK1/media", headers={"Range": "bytes=0-9"})
    assert prefix.status_code == 206
    assert prefix.headers["content-range"] == f"bytes 0-9/{size}"
    assert prefix.headers["content-length"] == "10"
    assert prefix.content == raw[:10]

    open_ended = client.get("/api/v1/clips/IG_COOK1/media", headers={"Range": "bytes=5-"})
    assert open_ended.status_code == 206
    assert open_ended.content == raw[5:]

    suffix = client.get("/api/v1/clips/IG_COOK1/media", headers={"Range": "bytes=-4"})
    assert suffix.status_code == 206
    assert suffix.content == raw[-4:]


def test_unsatisfiable_range_returns_416(tmp_path):
    client, library_dir = _setup(tmp_path)
    size = len((library_dir / "instagram" / "IG_COOK1.mp4").read_bytes())
    resp = client.get("/api/v1/clips/IG_COOK1/media", headers={"Range": "bytes=999999999-"})
    assert resp.status_code == 416
    assert resp.headers["content-range"] == f"bytes */{size}"


def test_conditional_request_returns_304(tmp_path):
    client, _ = _setup(tmp_path)
    etag = client.get("/api/v1/clips/IG_COOK1/media").headers["etag"]
    resp = client.get("/api/v1/clips/IG_COOK1/media", headers={"If-None-Match": etag})
    assert resp.status_code == 304
    assert resp.content == b""


def test_missing_and_unknown_media(tmp_path):
    client, _ = _setup(tmp_path)
    # IG_GONE is catalogued but its file was never written.
    gone = client.get("/api/v1/clips/IG_GONE/media")
    assert gone.status_code == 404
    assert gone.json()["error"]["code"] == "media_unavailable"

    unknown = client.get("/api/v1/clips/NOPE/media")
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "clip_not_found"


def test_media_requires_active_library(tmp_path):
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    client = TestClient(create_app(appstate), raise_server_exceptions=False)
    assert client.get("/api/v1/clips/IG_COOK1/media").status_code == 409
