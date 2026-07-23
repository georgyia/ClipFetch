"""The onboarding directory browser: sandboxed to home, dirs-only, traversal-proof."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from clipfetch.api.app import create_app  # noqa: E402
from clipfetch.appstate import AppState  # noqa: E402
from clipfetch.services import fs_service  # noqa: E402


def _home(tmp_path: Path) -> Path:
    """Build a fake home with a couple of folders, one a real library, plus a file to ignore."""
    home = tmp_path / "home"
    (home / "reels" / ".clipfetch").mkdir(parents=True)
    (home / "reels" / ".clipfetch" / "catalog.sqlite3").write_text("db")
    (home / "reels" / "instagram").mkdir()
    (home / "Documents").mkdir()
    (home / ".hidden").mkdir()
    (home / "notes.txt").write_text("secret contents")
    return home


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    home = _home(tmp_path)
    monkeypatch.setattr(fs_service, "_root", lambda: home.resolve())
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    return TestClient(create_app(appstate), raise_server_exceptions=False)


def test_lists_directories_and_flags_libraries(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    body = client.get("/api/v1/fs/dirs").json()

    assert body["at_root"] is True
    assert body["parent"] is None
    names = {e["name"] for e in body["entries"]}
    assert names == {"reels", "Documents"}  # dotfolders and files excluded
    reels = next(e for e in body["entries"] if e["name"] == "reels")
    assert reels["is_library"] is True
    assert next(e for e in body["entries"] if e["name"] == "Documents")["is_library"] is False


def test_never_lists_files_or_their_contents(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    raw = client.get("/api/v1/fs/dirs").text
    assert "notes.txt" not in raw
    assert "secret contents" not in raw


def test_navigates_into_a_subdirectory(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    home = fs_service._root()
    body = client.get("/api/v1/fs/dirs", params={"path": str(home / "reels")}).json()
    assert body["at_root"] is False
    assert body["parent"] == str(home)
    assert {e["name"] for e in body["entries"]} == {"instagram"}


def test_rejects_traversal_outside_home(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    home = fs_service._root()
    # Both an absolute escape and a ../ escape must be refused.
    escape = str(home / ".." / "..")
    assert client.get("/api/v1/fs/dirs", params={"path": str(home.parent)}).status_code == 400
    assert client.get("/api/v1/fs/dirs", params={"path": escape}).status_code == 400
    body = client.get("/api/v1/fs/dirs", params={"path": "/etc"})
    assert body.status_code == 400
    assert body.json()["error"]["code"] == "invalid_path"


def test_non_directory_path_is_rejected(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    home = fs_service._root()
    resp = client.get("/api/v1/fs/dirs", params={"path": str(home / "notes.txt")})
    assert resp.status_code == 400
