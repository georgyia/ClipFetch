"""Versioned SQLite catalog for a portable ClipFetch library."""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from clipfetch.model import Clip, ClipMetadata

CATALOG_DIR = ".clipfetch"
CATALOG_NAME = "catalog.sqlite3"
CURRENT_SCHEMA_VERSION = 2

_VIDEO_NAME = re.compile(r"^(reel|tiktok|short)_\d+_(.+)\.mp4$")
_PLATFORM_FOR_NOUN = {"reel": "instagram", "tiktok": "tiktok", "short": "youtube"}


class CatalogError(RuntimeError):
    """A catalog could not be opened, migrated, or updated."""


@dataclass(frozen=True)
class IndexReport:
    """Summary returned by :func:`index_library`."""

    scanned: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    missing: int = 0
    malformed_sidecars: int = 0


@dataclass(frozen=True)
class CatalogRecord:
    """Stable catalog fields shared by indexing and later query features."""

    platform: str
    clip_id: str
    relative_path: str
    file_size: int
    file_mtime_ns: int
    downloaded_at: str
    source_url: str | None
    author: str | None
    caption: str | None
    likes: int | None
    metadata_state: str
    available: bool = True
    hashtags: tuple[str, ...] = ()
    views: int | None = None
    comments_count: int | None = None
    shares: int | None = None
    duration_seconds: float | None = None
    published_at: str | None = None


Migration = Callable[[sqlite3.Connection], None]


def _migration_1(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE clips (
            platform TEXT NOT NULL,
            clip_id TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            file_mtime_ns INTEGER NOT NULL,
            downloaded_at TEXT NOT NULL,
            source_url TEXT,
            author TEXT,
            caption TEXT,
            likes INTEGER,
            metadata_state TEXT NOT NULL,
            available INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (platform, clip_id)
        )
        """
    )
    connection.execute("CREATE INDEX clips_path_idx ON clips(relative_path)")


def _migration_2(connection: sqlite3.Connection) -> None:
    for definition in (
        "hashtags_json TEXT NOT NULL DEFAULT '[]'",
        "views INTEGER",
        "comments_count INTEGER",
        "shares INTEGER",
        "duration_seconds REAL",
        "published_at TEXT",
    ):
        connection.execute(f"ALTER TABLE clips ADD COLUMN {definition}")


MIGRATIONS: dict[int, Migration] = {1: _migration_1, 2: _migration_2}


class Catalog:
    """Small thread-safe repository around one library's SQLite database."""

    def __init__(self, root: Path, connection: sqlite3.Connection) -> None:
        self.root = root.resolve()
        self.path = self.root / CATALOG_DIR / CATALOG_NAME
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.Lock()

    @classmethod
    def open(cls, root: Path) -> Catalog:
        root = root.resolve()
        connection: sqlite3.Connection | None = None
        try:
            (root / CATALOG_DIR).mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(
                root / CATALOG_DIR / CATALOG_NAME,
                timeout=10,
                check_same_thread=False,
            )
            connection.execute("PRAGMA foreign_keys = ON")
            _migrate(connection)
        except (OSError, sqlite3.Error) as err:
            try:
                if connection is not None:
                    connection.close()
            except sqlite3.Error:
                pass
            raise CatalogError(f"cannot open catalog in {root}: {err}") from err
        return cls(root, connection)

    @property
    def schema_version(self) -> int:
        row = self._connection.execute("SELECT version FROM schema_version").fetchone()
        return int(row[0])

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> Catalog:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def get(self, platform: str, clip_id: str) -> CatalogRecord | None:
        row = self._connection.execute(
            "SELECT * FROM clips WHERE platform = ? AND clip_id = ?",
            (platform, clip_id),
        ).fetchone()
        return _record_from_row(row) if row else None

    def all(self) -> list[CatalogRecord]:
        rows = self._connection.execute(
            "SELECT * FROM clips ORDER BY platform, clip_id"
        ).fetchall()
        return [_record_from_row(row) for row in rows]

    def upsert_download(self, clip: Clip, video_path: Path) -> str:
        """Insert/update a completed video and return its change classification."""
        resolved = video_path.resolve()
        try:
            relative = resolved.relative_to(self.root).as_posix()
        except ValueError as err:
            raise CatalogError(f"video is outside library root: {video_path}") from err
        stat = resolved.stat()
        existing = self.get(clip.platform, clip.ident)
        downloaded_at = (
            existing.downloaded_at if existing else datetime.now(timezone.utc).isoformat()
        )
        record = CatalogRecord(
            platform=clip.platform,
            clip_id=clip.ident,
            relative_path=relative,
            file_size=stat.st_size,
            file_mtime_ns=stat.st_mtime_ns,
            downloaded_at=downloaded_at,
            source_url=clip.url,
            author=clip.author,
            caption=clip.caption,
            likes=clip.likes,
            metadata_state="sidecar" if resolved.with_suffix(".json").exists() else "catalog",
            hashtags=clip.normalized_metadata().hashtags,
            views=clip.views,
            comments_count=clip.comments_count,
            shares=clip.shares,
            duration_seconds=clip.duration_seconds,
            published_at=(
                clip.published_at.astimezone(timezone.utc).isoformat()
                if clip.published_at
                else None
            ),
        )
        return self.upsert(record)

    def upsert(self, record: CatalogRecord) -> str:
        existing = self.get(record.platform, record.clip_id)
        if existing == record:
            return "unchanged"
        values = (
            record.platform,
            record.clip_id,
            record.relative_path,
            record.file_size,
            record.file_mtime_ns,
            record.downloaded_at,
            record.source_url,
            record.author,
            record.caption,
            record.likes,
            record.metadata_state,
            int(record.available),
            json.dumps(record.hashtags, ensure_ascii=False),
            record.views,
            record.comments_count,
            record.shares,
            record.duration_seconds,
            record.published_at,
        )
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO clips (
                    platform, clip_id, relative_path, file_size, file_mtime_ns,
                    downloaded_at, source_url, author, caption, likes,
                    metadata_state, available, hashtags_json, views,
                    comments_count, shares, duration_seconds, published_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(platform, clip_id) DO UPDATE SET
                    relative_path = excluded.relative_path,
                    file_size = excluded.file_size,
                    file_mtime_ns = excluded.file_mtime_ns,
                    downloaded_at = excluded.downloaded_at,
                    source_url = excluded.source_url,
                    author = excluded.author,
                    caption = excluded.caption,
                    likes = excluded.likes,
                    metadata_state = excluded.metadata_state,
                    available = excluded.available,
                    hashtags_json = excluded.hashtags_json,
                    views = excluded.views,
                    comments_count = excluded.comments_count,
                    shares = excluded.shares,
                    duration_seconds = excluded.duration_seconds,
                    published_at = excluded.published_at
                """,
                values,
            )
        return "updated" if existing else "inserted"

    def mark_missing_except(self, seen: set[tuple[str, str]]) -> int:
        missing = 0
        with self._lock, self._connection:
            for record in self.all():
                key = (record.platform, record.clip_id)
                if key not in seen:
                    missing += 1
                    if record.available:
                        self._connection.execute(
                            "UPDATE clips SET available = 0 WHERE platform = ? AND clip_id = ?",
                            key,
                        )
        return missing


def _migrate(connection: sqlite3.Connection) -> None:
    """Apply forward-only migrations atomically."""
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)"
        )
        row = connection.execute("SELECT version FROM schema_version").fetchone()
        version = int(row[0]) if row else 0
        if version > CURRENT_SCHEMA_VERSION:
            raise CatalogError(
                f"catalog schema {version} is newer than supported {CURRENT_SCHEMA_VERSION}"
            )
        for target in range(version + 1, CURRENT_SCHEMA_VERSION + 1):
            migration = MIGRATIONS[target]
            migration(connection)
            if row:
                connection.execute("UPDATE schema_version SET version = ?", (target,))
            else:
                connection.execute("INSERT INTO schema_version(version) VALUES (?)", (target,))
                row = (target,)
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def index_library(root: Path) -> IndexReport:
    """Reconcile supported video files and optional sidecars with the catalog."""
    root = root.resolve()
    if not root.is_dir():
        raise CatalogError(f"library directory does not exist: {root}")
    scanned = inserted = updated = unchanged = malformed = 0
    seen: set[tuple[str, str]] = set()
    with Catalog.open(root) as catalog:
        for path in sorted(root.glob("*.mp4")):
            match = _VIDEO_NAME.match(path.name)
            if not match or not path.is_file():
                continue
            scanned += 1
            noun, filename_id = match.groups()
            metadata, bad_sidecar = _read_sidecar(path.with_suffix(".json"))
            malformed += int(bad_sidecar)
            platform = _text(metadata.get("platform")) or _PLATFORM_FOR_NOUN[noun]
            clip_id = _text(metadata.get("id")) or filename_id
            normalized = ClipMetadata.from_dict(metadata)
            existing = catalog.get(platform, clip_id)
            stat = path.stat()
            downloaded_at = (
                existing.downloaded_at
                if existing
                else datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
            )
            record = CatalogRecord(
                platform=platform,
                clip_id=clip_id,
                relative_path=path.relative_to(root).as_posix(),
                file_size=stat.st_size,
                file_mtime_ns=stat.st_mtime_ns,
                downloaded_at=downloaded_at,
                source_url=normalized.url,
                author=normalized.author,
                caption=normalized.caption,
                likes=normalized.likes,
                metadata_state=(
                    "malformed"
                    if bad_sidecar
                    else "sidecar-v2"
                    if metadata.get("schema_version") == 2
                    else "legacy-sidecar"
                    if metadata
                    else "missing"
                ),
                hashtags=normalized.hashtags,
                views=normalized.views,
                comments_count=normalized.comments_count,
                shares=normalized.shares,
                duration_seconds=normalized.duration_seconds,
                published_at=(
                    normalized.published_at.isoformat() if normalized.published_at else None
                ),
            )
            state = catalog.upsert(record)
            inserted += int(state == "inserted")
            updated += int(state == "updated")
            unchanged += int(state == "unchanged")
            seen.add((platform, clip_id))
        missing = catalog.mark_missing_except(seen)
    return IndexReport(scanned, inserted, updated, unchanged, missing, malformed)


def record_completed_download(root: Path, video_path: Path, clip: Clip) -> None:
    """Catalog one completed download; safe to call from worker threads."""
    with Catalog.open(root) as catalog:
        catalog.upsert_download(clip, video_path)


def _read_sidecar(path: Path) -> tuple[dict[str, Any], bool]:
    if not path.exists():
        return {}, False
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}, True
    return (value, False) if isinstance(value, dict) else ({}, True)


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _record_from_row(row: sqlite3.Row) -> CatalogRecord:
    return CatalogRecord(
        platform=row["platform"],
        clip_id=row["clip_id"],
        relative_path=row["relative_path"],
        file_size=row["file_size"],
        file_mtime_ns=row["file_mtime_ns"],
        downloaded_at=row["downloaded_at"],
        source_url=row["source_url"],
        author=row["author"],
        caption=row["caption"],
        likes=row["likes"],
        metadata_state=row["metadata_state"],
        available=bool(row["available"]),
        hashtags=tuple(json.loads(row["hashtags_json"])),
        views=row["views"],
        comments_count=row["comments_count"],
        shares=row["shares"],
        duration_seconds=row["duration_seconds"],
        published_at=row["published_at"],
    )
