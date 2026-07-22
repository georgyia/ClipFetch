from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from clipfetch.api.app import create_app  # noqa: E402
from clipfetch.appstate import AppState  # noqa: E402
from tests.webfixtures import build_fixture_library  # noqa: E402


def _client(tmp_path: Path) -> TestClient:
    library_dir = tmp_path / "reels"
    build_fixture_library(library_dir)
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    client = TestClient(create_app(appstate), raise_server_exceptions=False)
    created = client.post(
        "/api/v1/libraries", json={"display_name": "Reels", "path": str(library_dir)}
    )
    client.post(f"/api/v1/libraries/{created.json()['id']}/activate")
    return client


def _ids(client: TestClient, query: str) -> list[str]:
    body = client.get("/api/v1/search", params={"q": query}).json()
    return [item["id"] for item in body["items"]]


def test_text_search_matches_caption_author_and_hashtags(tmp_path):
    client = _client(tmp_path)

    pasta = client.get("/api/v1/search", params={"q": "pasta"}).json()
    assert [item["id"] for item in pasta["items"]] == ["IG_COOK1"]
    assert pasta["total_matched"] == 1
    assert pasta["mode_used"] == "text"
    assert isinstance(pasta["semantic_available"], bool)

    assert _ids(client, "chefana") == ["IG_COOK1"]  # creator match
    assert _ids(client, "food") == ["IG_COOK1"]  # hashtag match


def test_search_ranks_by_term_frequency(tmp_path):
    client = _client(tmp_path)
    body = client.get("/api/v1/search", params={"q": "same reposted"}).json()
    ids = [item["id"] for item in body["items"]]
    assert set(ids) == {"IG_DUP_A", "IG_DUP_B"}
    assert ids[0] == "IG_DUP_B"  # contains both terms, so it outranks the single-term match


def test_semantic_mode_falls_back_to_text(tmp_path):
    client = _client(tmp_path)
    body = client.get("/api/v1/search", params={"q": "pasta", "mode": "meaning"}).json()
    assert body["requested_mode"] == "meaning"
    assert body["mode_used"] == "text"  # graceful fallback
    assert isinstance(body["semantic_available"], bool)


def test_pagination(tmp_path):
    client = _client(tmp_path)
    seen: set[str] = set()
    cursor = None
    pages = 0
    while True:
        params = {"q": "clip", "limit": 1}
        if cursor:
            params["cursor"] = cursor
        body = client.get("/api/v1/search", params=params).json()
        assert body["total_matched"] == 2
        seen.update(item["id"] for item in body["items"])
        cursor = body["next_cursor"]
        pages += 1
        if cursor is None:
            break
    assert seen == {"IG_DUP_A", "IG_DUP_B"}
    assert pages == 2


def test_invalid_mode_and_cursor_and_missing_query(tmp_path):
    client = _client(tmp_path)
    assert client.get("/api/v1/search", params={"q": "x", "mode": "bogus"}).json()["error"][
        "code"
    ] == "invalid_mode"
    bad = client.get("/api/v1/search", params={"q": "x", "cursor": "!!nope!!"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "invalid_cursor"
    assert client.get("/api/v1/search").status_code == 422  # q is required


def test_search_requires_active_library(tmp_path):
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    client = TestClient(create_app(appstate), raise_server_exceptions=False)
    assert client.get("/api/v1/search", params={"q": "x"}).status_code == 409
