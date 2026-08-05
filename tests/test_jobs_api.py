from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from clipfetch.api.app import create_app  # noqa: E402
from clipfetch.appstate import AppState  # noqa: E402
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
    return client, appstate


def test_enqueue_and_list_download_job(tmp_path):
    client, _ = _client(tmp_path)
    payload = {"kind": "download", "url": "https://x/p/1", "count": 5}
    resp = client.post("/api/v1/jobs", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["kind"] == "download"
    assert body["state"] == "queued"
    assert body["source_permalink"] == "https://x/p/1"
    assert "request" not in body  # raw request payload never leaks

    listed = client.get("/api/v1/jobs").json()["jobs"]
    assert any(job["id"] == body["id"] for job in listed)


def test_enqueue_is_idempotent_per_source(tmp_path):
    client, _ = _client(tmp_path)
    first = client.post("/api/v1/jobs", json={"kind": "download", "url": "https://x/p/1"})
    second = client.post("/api/v1/jobs", json={"kind": "download", "url": "https://x/p/1"})
    assert first.status_code == 201
    assert second.status_code == 200  # reused the active job
    assert first.json()["id"] == second.json()["id"]


def test_download_requires_url(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.post("/api/v1/jobs", json={"kind": "download"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "invalid_job"


def test_enqueue_feed_download_with_empty_url(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.post(
        "/api/v1/jobs", json={"kind": "download", "url": "", "count": 10, "quality": "high"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["source_permalink"] == ""
    assert body["state"] == "queued"


def test_unknown_kind_is_rejected(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.post("/api/v1/jobs", json={"kind": "wat", "url": "https://x/p/1"})
    assert resp.status_code == 422


def test_an_enrichment_needs_a_clip_and_a_target(tmp_path):
    """The payload is validated at enqueue, while the user is still looking at the button."""
    client, _ = _client(tmp_path)
    for payload in (
        {"kind": "enrich"},
        {"kind": "enrich", "clip_id": "IG_COOK1"},
        {"kind": "enrich", "clip_id": "IG_COOK1", "target": "vibes"},
    ):
        resp = client.post("/api/v1/jobs", json=payload)
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "invalid_job"
    assert client.get("/api/v1/jobs").json()["jobs"] == []


def test_enqueuing_an_enrichment_is_idempotent_per_clip_and_target(tmp_path):
    client, _ = _client(tmp_path)
    body = {"kind": "enrich", "clip_id": "IG_COOK1", "target": "comments"}

    first = client.post("/api/v1/jobs", json=body)
    second = client.post("/api/v1/jobs", json=body)
    assert first.status_code == 201 and second.status_code == 200
    assert first.json()["id"] == second.json()["id"]

    # A different target for the same clip is a different job.
    other = client.post(
        "/api/v1/jobs", json={"kind": "enrich", "clip_id": "IG_COOK1", "target": "transcript"}
    )
    assert other.status_code in (201, 422)  # 422 only when the transcribe extra is absent


def test_transcription_is_refused_when_the_extra_is_missing(tmp_path, monkeypatch):
    """Better to refuse now than to queue work that will certainly fail once it runs."""
    from clipfetch.api import capabilities

    monkeypatch.setattr(
        capabilities,
        "capability_matrix",
        lambda: {"transcription": {"available": False, "reason": "dependency_missing"}},
    )
    client, _ = _client(tmp_path)
    resp = client.post(
        "/api/v1/jobs", json={"kind": "enrich", "clip_id": "IG_COOK1", "target": "transcript"}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "transcription_unavailable"
    assert "clipfetch[transcribe]" in resp.json()["error"]["message"]
    assert client.get("/api/v1/jobs").json()["jobs"] == []


def test_transcription_is_accepted_when_the_extra_is_present(tmp_path, monkeypatch):
    from clipfetch.api import capabilities

    monkeypatch.setattr(
        capabilities, "capability_matrix", lambda: {"transcription": {"available": True}}
    )
    client, _ = _client(tmp_path)
    resp = client.post(
        "/api/v1/jobs", json={"kind": "enrich", "clip_id": "IG_COOK1", "target": "transcript"}
    )
    assert resp.status_code == 201
    assert resp.json()["kind"] == "enrich"


def test_cancel_queued_job(tmp_path):
    client, _ = _client(tmp_path)
    job = client.post("/api/v1/jobs", json={"kind": "download", "url": "https://x/p/1"}).json()
    cancelled = client.post(f"/api/v1/jobs/{job['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["state"] == "cancelled"


def test_events_replay_from_sequence(tmp_path):
    client, _ = _client(tmp_path)
    job = client.post("/api/v1/jobs", json={"kind": "download", "url": "https://x/p/1"}).json()
    body = client.get(f"/api/v1/jobs/{job['id']}/events").json()
    assert body["job"]["id"] == job["id"]
    assert [event["type"] for event in body["events"]] == ["enqueued"]
    # After the first sequence, no earlier events replay.
    after = client.get(f"/api/v1/jobs/{job['id']}/events?after=1").json()
    assert after["events"] == []


def test_stream_of_terminal_job_replays_and_ends(tmp_path):
    client, _ = _client(tmp_path)
    job = client.post("/api/v1/jobs", json={"kind": "download", "url": "https://x/p/1"}).json()
    client.post(f"/api/v1/jobs/{job['id']}/cancel")  # queued -> cancelled (terminal)
    resp = client.get(f"/api/v1/jobs/{job['id']}/stream")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "event: end" in resp.text
    assert "enqueued" in resp.text


def test_jobs_require_active_library(tmp_path):
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    client = TestClient(create_app(appstate), raise_server_exceptions=False)
    assert client.get("/api/v1/jobs").status_code == 409
