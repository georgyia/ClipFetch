from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from clipfetch.api.app import create_app  # noqa: E402
from clipfetch.appstate import AppState  # noqa: E402
from tests.webfixtures import build_fixture_library  # noqa: E402


def _client_with_library(tmp_path: Path) -> TestClient:
    library_dir = tmp_path / "reels"
    build_fixture_library(library_dir)
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    client = TestClient(create_app(appstate), raise_server_exceptions=False)
    created = client.post(
        "/api/v1/libraries", json={"display_name": "Reels", "path": str(library_dir)}
    )
    client.post(f"/api/v1/libraries/{created.json()['id']}/activate")
    return client


def test_poster_returns_cacheable_svg_placeholder(tmp_path):
    client = _client_with_library(tmp_path)
    resp = client.get("/api/v1/clips/IG_COOK1/poster")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    assert resp.headers["cache-control"] == "public, max-age=3600"
    assert resp.headers["etag"]
    assert resp.text.startswith("<svg") and 'aria-label="No poster available"' in resp.text
    # Deterministic: the same clip always yields the same bytes and never leaks the path.
    assert client.get("/api/v1/clips/IG_COOK1/poster").text == resp.text
    assert str(tmp_path) not in resp.text


def test_poster_conditional_returns_304(tmp_path):
    client = _client_with_library(tmp_path)
    etag = client.get("/api/v1/clips/IG_COOK1/poster").headers["etag"]
    conditional = client.get("/api/v1/clips/IG_COOK1/poster", headers={"If-None-Match": etag})
    assert conditional.status_code == 304
    assert conditional.content == b""


def test_poster_unknown_clip_is_404(tmp_path):
    client = _client_with_library(tmp_path)
    resp = client.get("/api/v1/clips/DOES_NOT_EXIST/poster")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "clip_not_found"


def test_poster_requires_active_library(tmp_path):
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    client = TestClient(create_app(appstate), raise_server_exceptions=False)
    assert client.get("/api/v1/clips/IG_COOK1/poster").status_code == 409
