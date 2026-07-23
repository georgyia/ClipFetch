from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from clipfetch.api.app import create_app  # noqa: E402
from clipfetch.appstate import AppState  # noqa: E402
from tests.webfixtures import build_fixture_library  # noqa: E402


def _client(tmp_path: Path):
    library_dir = tmp_path / "my-secret-reels"
    build_fixture_library(library_dir)
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    client = TestClient(create_app(appstate), raise_server_exceptions=False)
    created = client.post(
        "/api/v1/libraries",
        json={"display_name": "Private Journal Clips", "path": str(library_dir)},
    )
    client.post(f"/api/v1/libraries/{created.json()['id']}/activate")
    return client, library_dir


def test_bundle_reports_versions_counts_and_platforms(tmp_path):
    client, _ = _client(tmp_path)
    body = client.get("/api/v1/diagnostics").json()

    assert body["app_version"]
    assert body["schema"]["appstate"] >= 3
    assert body["schema"]["catalog"] >= 8
    assert body["libraries"]["count"] == 1
    assert body["libraries"]["active"]["clip_count"] >= 1
    assert "health" in body["libraries"]["active"]
    assert set(body["jobs"]) == {"queued", "running", "succeeded", "failed", "cancelled"}
    names = {entry["name"] for entry in body["platforms"]}
    assert {"Instagram", "TikTok", "YouTube"} <= names


def test_job_counts_reflect_the_queue(tmp_path):
    client, _ = _client(tmp_path)
    client.post("/api/v1/jobs", json={"kind": "download", "url": "https://x/p/1"})
    body = client.get("/api/v1/diagnostics").json()
    assert body["jobs"]["queued"] == 1


def test_bundle_is_redacted(tmp_path):
    """The bundle must never leak a filesystem path, library name, or source URL."""
    client, library_dir = _client(tmp_path)
    raw = client.get("/api/v1/diagnostics").text

    assert str(library_dir) not in raw
    assert "my-secret-reels" not in raw
    assert "Private Journal Clips" not in raw
    assert "example.invalid" not in raw  # fixture source urls
    # No absolute-looking path anywhere in the serialized bundle.
    bundle = json.loads(raw)
    for value in _all_strings(bundle):
        assert not value.startswith("/")
        assert "\\" not in value


def test_worker_state_not_configured_by_default(tmp_path):
    client, _ = _client(tmp_path)
    assert client.get("/api/v1/diagnostics").json()["worker"]["state"] == "not_configured"


def test_worker_state_running_when_provider_configured(tmp_path):
    from clipfetch.services.ingest_service import FakeSourceProvider

    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    app = create_app(appstate, provider=FakeSourceProvider())
    # The context-manager form runs the app lifespan, which starts the worker.
    with TestClient(app, raise_server_exceptions=False) as client:
        body = client.get("/api/v1/diagnostics").json()
    assert body["worker"]["state"] == "running"


def test_diagnostics_works_without_active_library(tmp_path):
    # A support bundle must be obtainable even when nothing is set up.
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    client = TestClient(create_app(appstate), raise_server_exceptions=False)
    body = client.get("/api/v1/diagnostics").json()
    assert body["libraries"]["count"] == 0
    assert body["libraries"]["active"] is None
    assert body["schema"]["catalog"] is None


def _all_strings(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _all_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _all_strings(item)
