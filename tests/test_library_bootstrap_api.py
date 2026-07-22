from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from clipfetch.api.app import create_app  # noqa: E402
from clipfetch.appstate import AppState  # noqa: E402
from tests.webfixtures import build_fixture_library  # noqa: E402


def _client(tmp_path: Path) -> TestClient:
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    return TestClient(create_app(appstate), raise_server_exceptions=False)


def test_bootstrap_empty(tmp_path):
    boot = _client(tmp_path).get("/api/v1/bootstrap").json()
    assert boot["active_library"] is None
    assert boot["libraries"] == []
    assert boot["app_version"]
    assert boot["worker"]["state"] == "not_configured"
    assert "semantic_search" in boot["capabilities"]


def test_register_list_activate_unregister_flow(tmp_path):
    library_dir = tmp_path / "reels"
    build_fixture_library(library_dir)
    client = _client(tmp_path)

    created = client.post(
        "/api/v1/libraries", json={"display_name": "Reels", "path": str(library_dir)}
    )
    assert created.status_code == 201
    summary = created.json()
    library_id = summary["id"]
    assert summary["health"] == "ready"
    assert summary["clip_count"] == 10
    assert summary["is_active"] is False

    listed = client.get("/api/v1/libraries").json()["libraries"]
    assert [item["id"] for item in listed] == [library_id]
    assert client.get("/api/v1/libraries/does-not-exist").status_code == 404

    activated = client.post(f"/api/v1/libraries/{library_id}/activate").json()
    assert activated["is_active"] is True
    assert activated["last_opened_at"] is not None
    assert client.get("/api/v1/bootstrap").json()["active_library"]["id"] == library_id

    assert client.delete(f"/api/v1/libraries/{library_id}").status_code == 204
    assert client.get("/api/v1/libraries").json()["libraries"] == []
    assert client.delete(f"/api/v1/libraries/{library_id}").status_code == 404
    # Unregistering never deletes the library's files.
    assert (library_dir / "instagram" / "IG_COOK1.mp4").is_file()


def test_register_rejects_bad_path_and_never_leaks_path(tmp_path):
    client = _client(tmp_path)

    bad = client.post(
        "/api/v1/libraries", json={"display_name": "Ghost", "path": str(tmp_path / "nope")}
    )
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "invalid_library"

    # A registered directory without a catalog reports as uninitialized, not ready.
    empty = tmp_path / "empty"
    empty.mkdir()
    resp = client.post("/api/v1/libraries", json={"display_name": "Empty", "path": str(empty)})
    summary = resp.json()
    assert summary["health"] == "uninitialized"
    assert summary["clip_count"] == 0
    # The on-disk path must never appear in a response body.
    assert "root_path" not in summary
    assert str(empty) not in resp.text
