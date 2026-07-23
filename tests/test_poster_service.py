from __future__ import annotations

from pathlib import Path

import pytest

from clipfetch.services import poster_service
from clipfetch.services.poster_service import (
    STATUS_ERROR,
    STATUS_EXISTS,
    STATUS_UNAVAILABLE,
    generate_poster,
    poster_path,
)
from tests.webfixtures import build_fixture_library


def test_poster_path_is_under_device_local_cache(tmp_path):
    path = poster_path(tmp_path, "instagram", "IG_COOK1")
    assert path == tmp_path / ".clipfetch" / "posters" / "instagram" / "IG_COOK1.jpg"


def test_generate_is_unavailable_without_ffmpeg(tmp_path, monkeypatch):
    monkeypatch.setattr(poster_service, "find_ffmpeg", lambda: None)
    root = tmp_path / "lib"
    build_fixture_library(root)
    result = generate_poster(root, "instagram", "IG_COOK1")
    assert result.status == STATUS_UNAVAILABLE
    assert result.path is None


def test_generate_errors_when_media_missing(tmp_path):
    root = tmp_path / "lib"
    build_fixture_library(root)
    # IG_GONE is catalogued but its media file was never written.
    result = generate_poster(root, "instagram", "IG_GONE")
    assert result.status == STATUS_ERROR


def test_generate_returns_exists_when_already_cached(tmp_path):
    root = tmp_path / "lib"
    build_fixture_library(root)
    cached = poster_path(root, "instagram", "IG_COOK1")
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(b"\xff\xd8\xff\xe0jpeg")
    result = generate_poster(root, "instagram", "IG_COOK1")
    assert result.status == STATUS_EXISTS
    assert result.path == cached


fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from clipfetch.api.app import create_app  # noqa: E402
from clipfetch.appstate import AppState  # noqa: E402


def _client(tmp_path: Path):
    library_dir = tmp_path / "reels"
    build_fixture_library(library_dir)
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    client = TestClient(create_app(appstate), raise_server_exceptions=False)
    created = client.post(
        "/api/v1/libraries", json={"display_name": "Reels", "path": str(library_dir)}
    )
    client.post(f"/api/v1/libraries/{created.json()['id']}/activate")
    return client, library_dir


def test_poster_endpoint_serves_placeholder_then_generated(tmp_path):
    client, library_dir = _client(tmp_path)

    # Before generation: the deterministic SVG placeholder.
    first = client.get("/api/v1/clips/IG_COOK1/media")  # ensure media exists
    assert first.status_code == 200
    placeholder = client.get("/api/v1/clips/IG_COOK1/poster")
    assert placeholder.status_code == 200
    assert placeholder.headers["content-type"].startswith("image/svg+xml")

    # After a poster is cached, the endpoint serves the JPEG.
    cached = poster_path(library_dir, "instagram", "IG_COOK1")
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(b"\xff\xd8\xff\xe0generated-jpeg")
    generated = client.get("/api/v1/clips/IG_COOK1/poster")
    assert generated.status_code == 200
    assert generated.headers["content-type"].startswith("image/jpeg")
    assert generated.content == b"\xff\xd8\xff\xe0generated-jpeg"

    # Conditional request against the generated poster returns 304.
    etag = generated.headers["etag"]
    not_modified = client.get(
        "/api/v1/clips/IG_COOK1/poster", headers={"If-None-Match": etag}
    )
    assert not_modified.status_code == 304
