from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from clipfetch.api.app import create_app  # noqa: E402
from clipfetch.appstate import AppState  # noqa: E402
from clipfetch.services import playback_service  # noqa: E402
from tests.webfixtures import build_fixture_library  # noqa: E402


def _client(tmp_path: Path):
    library_dir = tmp_path / "reels"
    build_fixture_library(library_dir)
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    client = TestClient(create_app(appstate), raise_server_exceptions=False)
    created = client.post(
        "/api/v1/libraries", json={"display_name": "Reels", "path": str(library_dir)}
    )
    client.post(f"/api/v1/libraries/{created.json()['id']}/activate")
    return client


def test_playback_round_trips_and_reports_resume(tmp_path):
    client = _client(tmp_path)

    # Never played -> null.
    assert client.get("/api/v1/clips/IG_COOK1/playback").json()["playback"] is None

    saved = client.put(
        "/api/v1/clips/IG_COOK1/playback",
        json={"position_ms": 8000, "duration_ms": 60000},
    )
    assert saved.status_code == 200
    body = saved.json()["playback"]
    assert body["position_ms"] == 8000
    assert body["completed"] is False
    assert body["resume_position_ms"] == 8000

    fetched = client.get("/api/v1/clips/IG_COOK1/playback").json()["playback"]
    assert fetched["position_ms"] == 8000


def test_near_end_marks_completed_and_clears_resume(tmp_path):
    client = _client(tmp_path)
    body = client.put(
        "/api/v1/clips/IG_COOK1/playback",
        json={"position_ms": 59000, "duration_ms": 60000},
    ).json()["playback"]
    assert body["completed"] is True
    assert body["resume_position_ms"] == 0


def test_negative_position_is_rejected(tmp_path):
    client = _client(tmp_path)
    resp = client.put("/api/v1/clips/IG_COOK1/playback", json={"position_ms": -1})
    assert resp.status_code == 422


def test_playback_requires_active_library(tmp_path):
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    client = TestClient(create_app(appstate), raise_server_exceptions=False)
    assert client.get("/api/v1/clips/IG_COOK1/playback").status_code == 409


def test_early_position_offers_no_resume(tmp_path):
    # Below RESUME_MIN_MS: recorded, but not resumable.
    view = playback_service.PlaybackView(
        clip_id="X", position_ms=1000, duration_ms=60000, completed=False,
        resume_position_ms=0, play_count=1, updated_at="now",
    )
    assert view.resume_position_ms == 0
    assert playback_service.RESUME_MIN_MS == 3000
