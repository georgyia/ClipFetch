"""Account connection: status + UI-triggered sign-in, exercised offline with fakes."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from clipfetch.api.app import create_app  # noqa: E402
from clipfetch.appstate import AppState  # noqa: E402
from clipfetch.platforms.instagram import Instagram  # noqa: E402
from clipfetch.services import accounts_service  # noqa: E402
from clipfetch.services.accounts_service import AccountManager  # noqa: E402


def _client(tmp_path: Path, manager: AccountManager) -> TestClient:
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    app = create_app(appstate)
    app.state.accounts = manager  # swap in a fake-backed manager
    return TestClient(app, raise_server_exceptions=False)


def _manager(**kwargs) -> AccountManager:
    # Synchronous spawn + display available by default, so connect() completes inline.
    kwargs.setdefault("display_available", lambda: True)
    kwargs.setdefault("spawn", lambda run: run())
    return AccountManager([Instagram()], **kwargs)


def test_status_lists_platforms_unknown_by_default(tmp_path):
    client = _client(tmp_path, _manager(connect_fn=lambda platform: None))
    body = client.get("/api/v1/accounts").json()
    entry = next(a for a in body["accounts"] if a["platform"] == "instagram")
    assert entry["label"] == "Instagram"
    assert entry["support"] == "full"
    assert entry["state"] == "unknown"
    assert entry["connected"] is False


def test_connect_marks_connected_on_success(tmp_path):
    calls = []
    client = _client(tmp_path, _manager(connect_fn=lambda platform: calls.append(platform.key)))
    body = client.post("/api/v1/accounts/instagram/connect").json()
    assert body["state"] == "connected"
    assert body["connected"] is True
    assert calls == ["instagram"]
    # Subsequent status reflects the connection.
    status = client.get("/api/v1/accounts").json()["accounts"][0]
    assert status["state"] == "connected"


def test_connect_marks_failed_when_sign_in_raises(tmp_path):
    def boom(platform):
        raise RuntimeError("window closed")

    client = _client(tmp_path, _manager(connect_fn=boom))
    assert client.post("/api/v1/accounts/instagram/connect").json()["state"] == "failed"


def test_connect_reports_no_display(tmp_path):
    client = _client(
        tmp_path, _manager(connect_fn=lambda platform: None, display_available=lambda: False)
    )
    body = client.post("/api/v1/accounts/instagram/connect").json()
    assert body["state"] == "no_display"
    assert body["connected"] is False


def test_connect_unknown_platform_is_404(tmp_path):
    client = _client(tmp_path, _manager(connect_fn=lambda platform: None))
    assert client.post("/api/v1/accounts/youtube/connect").status_code == 404


def test_status_never_leaks_paths_or_cookies(tmp_path):
    client = _client(tmp_path, _manager(connect_fn=lambda platform: None))
    raw = client.get("/api/v1/accounts").text
    assert "/" not in raw.replace("/api/v1/accounts", "")  # no filesystem paths
    assert "cookie" not in raw.lower()


def test_default_manager_covers_registered_platforms():
    keys = {entry["platform"] for entry in accounts_service.default_manager().status()["accounts"]}
    assert "instagram" in keys
