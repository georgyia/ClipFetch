"""One-origin static serving: the SPA loads and deep-links, without shadowing the API."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from clipfetch.api import static  # noqa: E402
from clipfetch.api.app import create_app  # noqa: E402
from clipfetch.appstate import AppState  # noqa: E402

INDEX_MARKER = "<div id=\"root\"></div><!-- clipfetch-watch -->"


def _bundle(tmp_path: Path) -> Path:
    bundle = tmp_path / "webui"
    (bundle / "assets").mkdir(parents=True)
    (bundle / "index.html").write_text(f"<!doctype html><html><body>{INDEX_MARKER}</body></html>")
    (bundle / "assets" / "app-abc123.js").write_text("console.log('clipfetch');")
    (bundle / "favicon.svg").write_text("<svg/>")
    return bundle


def _client(tmp_path: Path, monkeypatch, *, with_bundle: bool) -> TestClient:
    target = _bundle(tmp_path) if with_bundle else (tmp_path / "empty")
    target.mkdir(exist_ok=True)
    monkeypatch.setenv("CLIPFETCH_WEBUI_DIR", str(target))
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    return TestClient(create_app(appstate), raise_server_exceptions=False)


def test_serves_index_at_root(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, with_bundle=True)
    resp = client.get("/")
    assert resp.status_code == 200
    assert INDEX_MARKER in resp.text


def test_client_side_route_falls_back_to_index(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, with_bundle=True)
    resp = client.get("/explore/topic/cooking")
    assert resp.status_code == 200
    assert INDEX_MARKER in resp.text  # deep link / refresh loads the app shell


def test_serves_hashed_asset_and_root_file(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, with_bundle=True)
    assert client.get("/assets/app-abc123.js").status_code == 200
    assert client.get("/favicon.svg").text == "<svg/>"


def test_api_paths_are_never_shadowed_by_spa(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, with_bundle=True)
    # Health and capabilities keep serving JSON with the bundle mounted.
    assert client.get("/health/live").json() == {"status": "ok"}
    # An unknown API path is a JSON 404, not the HTML shell.
    resp = client.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    assert INDEX_MARKER not in resp.text
    assert resp.headers["content-type"].startswith("application/json")


def test_api_only_when_no_bundle(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, with_bundle=False)
    assert static.bundle_dir() is None
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/").status_code == 404  # no SPA route mounted


def test_safe_file_blocks_traversal(tmp_path, monkeypatch):
    bundle = _bundle(tmp_path)
    outside = tmp_path / "secret.txt"
    outside.write_text("top secret")
    assert static._safe_file(bundle, "../secret.txt") is None
    assert static._safe_file(bundle, "assets/app-abc123.js") is not None
    assert static._safe_file(bundle, "") is None
