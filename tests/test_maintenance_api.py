from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from clipfetch.api.app import create_app  # noqa: E402
from clipfetch.appstate import AppState  # noqa: E402
from clipfetch.catalog import Catalog, CatalogError  # noqa: E402
from clipfetch.services import maintenance_service  # noqa: E402
from tests.webfixtures import build_fixture_library  # noqa: E402

#: The fixture library ships one clip whose media file is deliberately absent.
GONE = "IG_GONE"
PRESENT = "IG_COOK1"


def _client(tmp_path: Path) -> tuple[TestClient, Path]:
    library_dir = tmp_path / "reels"
    build_fixture_library(library_dir)
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    client = TestClient(create_app(appstate), raise_server_exceptions=False)
    created = client.post(
        "/api/v1/libraries", json={"display_name": "Reels", "path": str(library_dir)}
    )
    client.post(f"/api/v1/libraries/{created.json()['id']}/activate")
    return client, library_dir


def _path_of(library_dir: Path, clip_id: str) -> Path:
    with Catalog.open(library_dir) as catalog:
        record = next(item for item in catalog.all() if item.clip_id == clip_id)
    return library_dir / record.relative_path


def test_missing_clips_are_listable_with_where_the_file_used_to_be(tmp_path):
    client, _ = _client(tmp_path)
    body = client.get("/api/v1/maintenance/missing").json()

    ids = [item["id"] for item in body["items"]]
    assert GONE in ids
    assert PRESENT not in ids  # present media never appears in the triage list
    entry = next(item for item in body["items"] if item["id"] == GONE)
    # The path is what makes the row actionable, and it is library-relative like the exports.
    assert entry["relative_path"] and not entry["relative_path"].startswith("/")
    assert entry["available"] is False


def test_the_listing_never_carries_an_absolute_path(tmp_path):
    client, library_dir = _client(tmp_path)
    resp = client.get("/api/v1/maintenance/missing")
    assert str(library_dir) not in resp.text
    assert str(tmp_path) not in resp.text


def test_forgetting_removes_the_record_and_leaves_the_library_untouched(tmp_path):
    client, library_dir = _client(tmp_path)
    before = sorted(path.name for path in library_dir.rglob("*.mp4"))

    report = client.post("/api/v1/maintenance/missing/forget", json={"clip_ids": [GONE]})
    assert report.status_code == 200
    assert report.json()["forgotten"] == [GONE]

    # The record is gone from the catalog...
    assert client.get(f"/api/v1/clips/{GONE}").status_code == 404
    assert GONE not in [
        item["id"] for item in client.get("/api/v1/maintenance/missing").json()["items"]
    ]
    # ...and not one media file was touched.
    assert sorted(path.name for path in library_dir.rglob("*.mp4")) == before


def test_forgetting_a_clip_whose_file_is_present_is_refused(tmp_path):
    """This is the guard that stops a stale triage list from becoming a delete button."""
    client, _ = _client(tmp_path)

    report = client.post("/api/v1/maintenance/missing/forget", json={"clip_ids": [PRESENT]})
    assert report.json() == {"forgotten": [], "kept": [PRESENT], "unknown": []}
    assert client.get(f"/api/v1/clips/{PRESENT}").status_code == 200


def test_a_restored_file_is_no_longer_reported_missing(tmp_path):
    client, library_dir = _client(tmp_path)
    restored = _path_of(library_dir, GONE)
    restored.parent.mkdir(parents=True, exist_ok=True)
    restored.write_bytes(b"the file came back")

    body = client.get("/api/v1/maintenance/missing").json()
    assert GONE not in [item["id"] for item in body["items"]]
    # And forgetting now refuses it, because presence is checked against disk, not the stored flag.
    report = client.post("/api/v1/maintenance/missing/forget", json={"clip_ids": [GONE]})
    assert report.json()["kept"] == [GONE]


def test_re_indexing_a_restored_clip_brings_it_back_after_forgetting(tmp_path):
    """Forgetting is not permanent loss: the file is the source of truth, and indexing rebuilds.

    Built from a downloader-named file rather than the web fixture, whose paths
    (``instagram/IG_GONE.mp4``) do not match the indexer's filename convention and so cannot be
    rediscovered by design.
    """
    from clipfetch.catalog import index_library
    from clipfetch.library import find_clip

    library = tmp_path / "reels"
    library.mkdir()
    video = library / "reel_001_ABC.mp4"
    video.write_bytes(b"video")
    index_library(library)
    video.unlink()

    assert maintenance_service.forget_clips(library, ["ABC"]).forgotten == ("ABC",)
    with pytest.raises(CatalogError):
        find_clip(library, "ABC")

    video.write_bytes(b"restored from a backup")
    index_library(library)
    assert find_clip(library, "ABC").clip_id == "ABC"


def test_forgetting_drops_the_clip_from_its_topics(tmp_path):
    client, library_dir = _client(tmp_path)
    with Catalog.open(library_dir) as catalog:
        record = next(item for item in catalog.all() if item.clip_id == GONE)
        catalog.set_manual_topic(record.platform, record.clip_id, "food")
        assert catalog.topic_names(record.platform, record.clip_id)

    client.post("/api/v1/maintenance/missing/forget", json={"clip_ids": [GONE]})

    with Catalog.open(library_dir) as catalog:
        assert catalog.topic_names(record.platform, record.clip_id) == ()


def test_unknown_ids_are_reported_rather_than_failing_the_batch(tmp_path):
    client, _ = _client(tmp_path)
    report = client.post(
        "/api/v1/maintenance/missing/forget", json={"clip_ids": [GONE, "NEVER_EXISTED"]}
    ).json()
    assert report["forgotten"] == [GONE]
    assert report["unknown"] == ["NEVER_EXISTED"]


def test_forget_validates_its_request_and_needs_a_library(tmp_path):
    client, _ = _client(tmp_path)
    assert (
        client.post("/api/v1/maintenance/missing/forget", json={"clip_ids": []}).status_code == 422
    )

    appstate = AppState.open(tmp_path / "other.sqlite3")
    bare = TestClient(create_app(appstate), raise_server_exceptions=False)
    assert bare.get("/api/v1/maintenance/missing").status_code == 409


def test_listing_pages(tmp_path):
    _, library_dir = _client(tmp_path)
    # Make a second clip missing so paging has something to page.
    _path_of(library_dir, PRESENT).unlink()

    first = maintenance_service.list_missing(library_dir, limit=1)
    assert len(first.items) == 1 and first.total == 2 and first.next_offset == 1
    second = maintenance_service.list_missing(library_dir, limit=1, offset=1)
    assert len(second.items) == 1 and second.next_offset is None
    assert first.items[0].clip["id"] != second.items[0].clip["id"]
