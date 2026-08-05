from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from clipfetch.api.app import create_app  # noqa: E402
from clipfetch.appstate import AppState  # noqa: E402
from clipfetch.catalog import Catalog  # noqa: E402
from clipfetch.services import enrichment_service  # noqa: E402
from tests.webfixtures import build_fixture_library  # noqa: E402

TRANSCRIBED = "IG_COOK1"
COMMENTED = "IG_TECH1"
BARE = "IG_TRAVEL1"


def _library(tmp_path: Path) -> Path:
    library_dir = tmp_path / "reels"
    build_fixture_library(library_dir)
    with Catalog.open(library_dir) as catalog:
        catalog.set_transcript(
            "instagram",
            TRANSCRIBED,
            text="boil the pasta in salted water",
            language="en",
            model_id="fake/base",
            model_revision="v1",
            source_hash="hash",
            processing_seconds=1.5,
            status="complete",
        )
        catalog.set_comments(
            "instagram",
            COMMENTED,
            [(f"c{index}", f"comment {index}") for index in range(5)],
            status="complete",
        )
    return library_dir


def _client(tmp_path: Path) -> TestClient:
    library_dir = _library(tmp_path)
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    client = TestClient(create_app(appstate), raise_server_exceptions=False)
    created = client.post(
        "/api/v1/libraries", json={"display_name": "Reels", "path": str(library_dir)}
    )
    client.post(f"/api/v1/libraries/{created.json()['id']}/activate")
    return client


def test_transcript_is_readable_with_its_provenance(tmp_path):
    client = _client(tmp_path)
    body = client.get(f"/api/v1/clips/{TRANSCRIBED}/transcript").json()

    assert body["text"] == "boil the pasta in salted water"
    assert body["status"] == "complete" and body["language"] == "en"
    # Provenance is the point: a transcript you cannot attribute is not checkable.
    assert body["model_id"] == "fake/base" and body["model_revision"] == "v1"
    assert body["updated_at"] and body["truncated"] is False


def test_a_clip_that_was_never_transcribed_is_not_an_error(tmp_path):
    client = _client(tmp_path)
    resp = client.get(f"/api/v1/clips/{BARE}/transcript")

    # "No transcript" is a state of a known clip, not a missing resource.
    assert resp.status_code == 200
    assert resp.json()["status"] is None and resp.json()["text"] is None
    assert resp.json()["character_count"] == 0


def test_a_long_transcript_is_capped_and_says_so(tmp_path):
    library_dir = _library(tmp_path)
    full = "word " * (enrichment_service.MAX_TRANSCRIPT_CHARACTERS // 2)
    with Catalog.open(library_dir) as catalog:
        catalog.set_transcript(
            "instagram",
            TRANSCRIBED,
            text=full,
            language="en",
            model_id="fake/base",
            model_revision="v1",
            source_hash="hash2",
            processing_seconds=1.0,
            status="complete",
        )

    view = enrichment_service.get_transcript(library_dir, TRANSCRIBED)
    assert view.truncated is True
    assert len(view.text) == enrichment_service.MAX_TRANSCRIPT_CHARACTERS
    # The count describes the stored transcript, not the truncated copy.
    assert view.character_count == len(full)


def test_a_failed_transcript_never_leaks_the_backend_error(tmp_path):
    """``transcript_error`` holds ``str(exception)``, which can name local media paths."""
    library_dir = _library(tmp_path)
    secret = "/Users/someone/Movies/private/reel_001_IG_COOK1.mp4"
    with Catalog.open(library_dir) as catalog:
        catalog.set_transcript(
            "instagram",
            TRANSCRIBED,
            text=None,
            language=None,
            model_id="fake/base",
            model_revision="v1",
            source_hash="hash3",
            processing_seconds=0.2,
            status="failed",
            error=f"could not decode {secret}",
        )
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    client = TestClient(create_app(appstate), raise_server_exceptions=False)
    created = client.post(
        "/api/v1/libraries", json={"display_name": "Reels", "path": str(library_dir)}
    )
    client.post(f"/api/v1/libraries/{created.json()['id']}/activate")

    resp = client.get(f"/api/v1/clips/{TRANSCRIBED}/transcript")
    assert resp.json()["status"] == "failed"
    assert secret not in resp.text
    assert "could not decode" not in resp.text


def test_comments_paginate_and_report_the_snapshot_time(tmp_path):
    client = _client(tmp_path)
    first = client.get(f"/api/v1/clips/{COMMENTED}/comments?limit=2").json()

    assert [item["text"] for item in first["items"]] == ["comment 0", "comment 1"]
    assert first["total"] == 5 and first["next_offset"] == 2
    assert first["status"] == "complete"
    # Comments are a local snapshot; without a capture time the reader cannot judge them.
    assert first["retrieved_at"]

    last = client.get(f"/api/v1/clips/{COMMENTED}/comments?limit=2&offset=4").json()
    assert [item["text"] for item in last["items"]] == ["comment 4"]
    assert last["next_offset"] is None


def test_a_clip_without_comments_returns_an_empty_page(tmp_path):
    client = _client(tmp_path)
    body = client.get(f"/api/v1/clips/{BARE}/comments").json()
    assert body["items"] == [] and body["total"] == 0 and body["status"] is None


def test_unknown_clips_are_404_on_both_endpoints(tmp_path):
    client = _client(tmp_path)
    for path in ("transcript", "comments"):
        resp = client.get(f"/api/v1/clips/NOPE/{path}")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "clip_not_found"


def test_responses_never_carry_device_paths(tmp_path):
    client = _client(tmp_path)
    for path in ("transcript", "comments"):
        resp = client.get(f"/api/v1/clips/{TRANSCRIBED}/{path}")
        assert str(tmp_path) not in resp.text
        assert "relative_path" not in resp.text
