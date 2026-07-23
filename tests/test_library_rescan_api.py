"""Rescan re-indexes a library from disk so out-of-band files (or downloads) appear."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from clipfetch.api.app import create_app  # noqa: E402
from clipfetch.appstate import AppState  # noqa: E402


def _client(tmp_path: Path):
    library_dir = tmp_path / "reels"
    library_dir.mkdir()
    (library_dir / "reel_001_AAA.mp4").write_bytes(b"video-aaa")
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    client = TestClient(create_app(appstate), raise_server_exceptions=False)
    created = client.post(
        "/api/v1/libraries", json={"display_name": "Reels", "path": str(library_dir)}
    )
    lib_id = created.json()["id"]
    client.post(f"/api/v1/libraries/{lib_id}/activate")
    return client, library_dir, lib_id


def test_rescan_indexes_new_files(tmp_path):
    client, library_dir, lib_id = _client(tmp_path)

    (library_dir / "reel_002_BBB.mp4").write_bytes(b"video-bbb")
    resp = client.post(f"/api/v1/libraries/{lib_id}/rescan")

    assert resp.status_code == 200
    body = resp.json()
    assert body["report"]["scanned"] >= 2
    assert body["report"]["inserted"] >= 1
    assert body["library"]["clip_count"] >= 2


def test_rescan_report_is_redacted(tmp_path):
    """The rescan response carries counts and the summary, never a filesystem path."""
    client, library_dir, lib_id = _client(tmp_path)
    resp = client.post(f"/api/v1/libraries/{lib_id}/rescan")
    assert str(library_dir) not in resp.text
    library = resp.json()["library"]
    assert "root_path" not in library and "path" not in library


def test_rescan_unknown_library_is_404(tmp_path):
    client, _, _ = _client(tmp_path)
    assert client.post("/api/v1/libraries/nope/rescan").status_code == 404
