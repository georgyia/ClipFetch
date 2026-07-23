import json
import sqlite3
from pathlib import Path

import pytest

from clipfetch.catalog import Catalog, CatalogError, index_library
from clipfetch.model import Clip


def _video(root: Path, name: str = "reel_001_ABC.mp4", body: bytes = b"video") -> Path:
    path = root / name
    path.write_bytes(body)
    return path


def test_catalog_creation_reopening_and_unique_upsert(tmp_path):
    video = _video(tmp_path)
    clip = Clip(
        "instagram",
        "ABC",
        "https://expiring.invalid/video",
        url="https://www.instagram.com/reel/ABC/",
        author="nasa",
        caption="space",
        likes=42,
    )
    with Catalog.open(tmp_path) as catalog:
        assert catalog.schema_version == 9
        assert catalog.upsert_download(clip, video) == "inserted"
        assert catalog.upsert_download(clip, video) == "unchanged"

    with Catalog.open(tmp_path) as reopened:
        record = reopened.get("instagram", "ABC")
        assert record is not None
        assert record.relative_path == "reel_001_ABC.mp4"
        assert record.file_size == 5
        assert record.source_url == "https://www.instagram.com/reel/ABC/"
        # Expiring transport URLs are deliberately never persisted.
        values = reopened._connection.execute("SELECT * FROM clips").fetchone()
        assert "expiring.invalid" not in repr(tuple(values))


def test_relative_path_survives_moving_complete_library(tmp_path):
    original = tmp_path / "original"
    original.mkdir()
    video = _video(original)
    with Catalog.open(original) as catalog:
        catalog.upsert_download(Clip("instagram", "ABC", "cdn"), video)
    moved = tmp_path / "moved"
    original.rename(moved)
    with Catalog.open(moved) as catalog:
        record = catalog.get("instagram", "ABC")
        assert record is not None
        assert (moved / record.relative_path).read_bytes() == b"video"


def test_index_sidecars_is_idempotent_and_marks_missing(tmp_path):
    rich = _video(tmp_path)
    rich.with_suffix(".json").write_text(
        json.dumps(
            {
                "platform": "instagram",
                "id": "ABC",
                "url": "https://instagram.test/reel/ABC/",
                "author": "nasa",
                "caption": "space",
                "likes": 10,
            }
        ),
        encoding="utf-8",
    )
    _video(tmp_path, "tiktok_002_DEF.mp4", b"other")
    _video(tmp_path, "reel_003_BAD.mp4").with_suffix(".json").write_text(
        "{bad", encoding="utf-8"
    )

    first = index_library(tmp_path)
    assert (first.scanned, first.inserted, first.malformed_sidecars) == (3, 3, 1)
    second = index_library(tmp_path)
    assert (second.inserted, second.updated, second.unchanged) == (0, 0, 3)

    rich.unlink()
    third = index_library(tmp_path)
    assert third.missing == 1
    with Catalog.open(tmp_path) as catalog:
        assert catalog.get("instagram", "ABC").available is False


def test_index_refreshes_changed_file(tmp_path):
    video = _video(tmp_path)
    index_library(tmp_path)
    video.write_bytes(b"larger video")
    report = index_library(tmp_path)
    assert report.updated == 1
    with Catalog.open(tmp_path) as catalog:
        assert catalog.get("instagram", "ABC").file_size == len(b"larger video")


def test_failed_schema_migration_rolls_back(tmp_path, monkeypatch):
    from clipfetch import catalog as module

    database_dir = tmp_path / ".clipfetch"
    database_dir.mkdir()
    connection = sqlite3.connect(database_dir / "catalog.sqlite3")
    connection.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
    connection.execute("INSERT INTO schema_version VALUES (0)")
    connection.commit()
    connection.close()

    def broken(connection):
        connection.execute("CREATE TABLE should_rollback (value TEXT)")
        raise sqlite3.OperationalError("boom")

    monkeypatch.setitem(module.MIGRATIONS, 1, broken)
    with pytest.raises(CatalogError, match="boom"):
        Catalog.open(tmp_path)

    connection = sqlite3.connect(database_dir / "catalog.sqlite3")
    names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
    assert "should_rollback" not in names
    assert connection.execute("SELECT version FROM schema_version").fetchone()[0] == 0


def test_v1_catalog_migrates_without_losing_existing_metadata(tmp_path):
    from clipfetch.catalog import MIGRATIONS

    database_dir = tmp_path / ".clipfetch"
    database_dir.mkdir()
    connection = sqlite3.connect(database_dir / "catalog.sqlite3")
    connection.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
    connection.execute("INSERT INTO schema_version VALUES (1)")
    MIGRATIONS[1](connection)
    connection.execute(
        """
        INSERT INTO clips VALUES (
            'instagram', 'OLD', 'reel_001_OLD.mp4', 10, 20,
            '2026-01-01T00:00:00+00:00', NULL, 'nasa', 'space', 42, 'sidecar', 1
        )
        """
    )
    connection.commit()
    connection.close()

    with Catalog.open(tmp_path) as catalog:
        assert catalog.schema_version == 9
        record = catalog.get("instagram", "OLD")
        assert record is not None
        assert (record.author, record.caption, record.likes) == ("nasa", "space", 42)
        assert record.views is None and record.hashtags == ()


def test_missing_library_is_actionable(tmp_path):
    with pytest.raises(CatalogError, match="does not exist"):
        index_library(tmp_path / "missing")
