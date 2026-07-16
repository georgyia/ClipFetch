"""Versioned SQLite catalog for a portable ClipFetch library."""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from clipfetch.model import Clip, ClipMetadata

CATALOG_DIR = ".clipfetch"
CATALOG_NAME = "catalog.sqlite3"
CURRENT_SCHEMA_VERSION = 8

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
    transcript_text: str | None = None
    transcript_language: str | None = None
    transcript_model_id: str | None = None
    transcript_model_revision: str | None = None
    transcript_source_hash: str | None = None
    transcript_processing_seconds: float | None = None
    transcript_status: str | None = None
    transcript_error: str | None = None
    transcript_updated_at: str | None = None
    comment_text: str | None = None
    comment_status: str | None = None
    comment_retrieved_at: str | None = None
    comment_error: str | None = None
    visible_text: str | None = None
    visible_text_segments: tuple[VisibleTextSegment, ...] = ()
    visible_text_confidence: float | None = None
    visible_text_model_id: str | None = None
    visible_text_model_revision: str | None = None
    visible_text_source_hash: str | None = None
    visible_text_sample_policy: str | None = None
    visible_text_processing_seconds: float | None = None
    visible_text_status: str | None = None
    visible_text_error: str | None = None
    visible_text_updated_at: str | None = None


@dataclass(frozen=True)
class VisibleTextSegment:
    """One retained OCR line and its representative video timestamp."""

    timestamp_seconds: float
    text: str
    confidence: float


@dataclass(frozen=True)
class CatalogComment:
    """One retained comment without commenter identity or profile metadata."""

    platform: str
    clip_id: str
    comment_id: str
    text: str
    retrieved_at: str


@dataclass(frozen=True)
class MediaSignature:
    """Cached exact/perceptual signature for one specific file revision."""

    platform: str
    clip_id: str
    file_hash: str
    file_size: int
    file_mtime_ns: int
    algorithm_version: str
    duration_seconds: float | None
    frame_hashes: tuple[int, ...]
    status: str
    error: str | None
    generated_at: str


@dataclass(frozen=True)
class EmbeddingRecord:
    """One normalized semantic vector and the identity of its exact input/model."""

    platform: str
    clip_id: str
    model_id: str
    model_revision: str
    input_hash: str
    dimension: int
    vector: bytes
    generated_at: str


@dataclass(frozen=True)
class TopicAssignment:
    platform: str
    clip_id: str
    topic: str
    confidence: float
    provenance: str
    model_id: str | None
    model_revision: str | None
    definition_hash: str | None
    input_hash: str | None
    threshold: float | None
    generated_at: str


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


def _migration_3(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE semantic_embeddings (
            platform TEXT NOT NULL,
            clip_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            model_revision TEXT NOT NULL,
            input_hash TEXT NOT NULL,
            dimension INTEGER NOT NULL,
            vector BLOB NOT NULL,
            generated_at TEXT NOT NULL,
            PRIMARY KEY (platform, clip_id, model_id, model_revision),
            FOREIGN KEY (platform, clip_id) REFERENCES clips(platform, clip_id)
                ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        "CREATE INDEX semantic_model_idx "
        "ON semantic_embeddings(model_id, model_revision)"
    )


def _migration_4(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE topic_assignments (
            platform TEXT NOT NULL,
            clip_id TEXT NOT NULL,
            topic TEXT NOT NULL,
            confidence REAL NOT NULL,
            provenance TEXT NOT NULL,
            model_id TEXT,
            model_revision TEXT,
            definition_hash TEXT,
            input_hash TEXT,
            threshold REAL,
            generated_at TEXT NOT NULL,
            PRIMARY KEY (platform, clip_id, topic, provenance),
            FOREIGN KEY (platform, clip_id) REFERENCES clips(platform, clip_id)
                ON DELETE CASCADE
        )
        """
    )
    connection.execute("CREATE INDEX topic_name_idx ON topic_assignments(topic)")


def _migration_5(connection: sqlite3.Connection) -> None:
    for definition in (
        "transcript_text TEXT",
        "transcript_language TEXT",
        "transcript_model_id TEXT",
        "transcript_model_revision TEXT",
        "transcript_source_hash TEXT",
        "transcript_processing_seconds REAL",
        "transcript_status TEXT",
        "transcript_error TEXT",
        "transcript_updated_at TEXT",
    ):
        connection.execute(f"ALTER TABLE clips ADD COLUMN {definition}")


def _migration_6(connection: sqlite3.Connection) -> None:
    for definition in (
        "comment_text TEXT",
        "comment_status TEXT",
        "comment_retrieved_at TEXT",
        "comment_error TEXT",
    ):
        connection.execute(f"ALTER TABLE clips ADD COLUMN {definition}")
    connection.execute(
        """
        CREATE TABLE clip_comments (
            platform TEXT NOT NULL,
            clip_id TEXT NOT NULL,
            comment_id TEXT NOT NULL,
            text TEXT NOT NULL,
            retrieved_at TEXT NOT NULL,
            PRIMARY KEY (platform, clip_id, comment_id),
            FOREIGN KEY (platform, clip_id) REFERENCES clips(platform, clip_id)
                ON DELETE CASCADE
        )
        """
    )


def _migration_7(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE media_signatures (
            platform TEXT NOT NULL,
            clip_id TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            file_mtime_ns INTEGER NOT NULL,
            algorithm_version TEXT NOT NULL,
            duration_seconds REAL,
            frame_hashes_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL,
            error TEXT,
            generated_at TEXT NOT NULL,
            PRIMARY KEY (platform, clip_id),
            FOREIGN KEY (platform, clip_id) REFERENCES clips(platform, clip_id)
                ON DELETE CASCADE
        )
        """
    )
    connection.execute("CREATE INDEX media_signature_hash_idx ON media_signatures(file_hash)")


def _migration_8(connection: sqlite3.Connection) -> None:
    for definition in (
        "visible_text TEXT",
        "visible_text_segments_json TEXT NOT NULL DEFAULT '[]'",
        "visible_text_confidence REAL",
        "visible_text_model_id TEXT",
        "visible_text_model_revision TEXT",
        "visible_text_source_hash TEXT",
        "visible_text_sample_policy TEXT",
        "visible_text_processing_seconds REAL",
        "visible_text_status TEXT",
        "visible_text_error TEXT",
        "visible_text_updated_at TEXT",
    ):
        connection.execute(f"ALTER TABLE clips ADD COLUMN {definition}")


MIGRATIONS: dict[int, Migration] = {
    1: _migration_1,
    2: _migration_2,
    3: _migration_3,
    4: _migration_4,
    5: _migration_5,
    6: _migration_6,
    7: _migration_7,
    8: _migration_8,
}


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
        if existing and record.transcript_model_id is None:
            record = replace(
                record,
                transcript_text=existing.transcript_text,
                transcript_language=existing.transcript_language,
                transcript_model_id=existing.transcript_model_id,
                transcript_model_revision=existing.transcript_model_revision,
                transcript_source_hash=existing.transcript_source_hash,
                transcript_processing_seconds=existing.transcript_processing_seconds,
                transcript_status=existing.transcript_status,
                transcript_error=existing.transcript_error,
                transcript_updated_at=existing.transcript_updated_at,
            )
        if existing and record.comment_status is None:
            record = replace(
                record,
                comment_text=existing.comment_text,
                comment_status=existing.comment_status,
                comment_retrieved_at=existing.comment_retrieved_at,
                comment_error=existing.comment_error,
            )
        if existing and record.visible_text_model_id is None:
            record = replace(
                record,
                visible_text=existing.visible_text,
                visible_text_segments=existing.visible_text_segments,
                visible_text_confidence=existing.visible_text_confidence,
                visible_text_model_id=existing.visible_text_model_id,
                visible_text_model_revision=existing.visible_text_model_revision,
                visible_text_source_hash=existing.visible_text_source_hash,
                visible_text_sample_policy=existing.visible_text_sample_policy,
                visible_text_processing_seconds=existing.visible_text_processing_seconds,
                visible_text_status=existing.visible_text_status,
                visible_text_error=existing.visible_text_error,
                visible_text_updated_at=existing.visible_text_updated_at,
            )
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

    def get_embedding(
        self, platform: str, clip_id: str, model_id: str, model_revision: str
    ) -> EmbeddingRecord | None:
        row = self._connection.execute(
            """
            SELECT * FROM semantic_embeddings
            WHERE platform = ? AND clip_id = ? AND model_id = ? AND model_revision = ?
            """,
            (platform, clip_id, model_id, model_revision),
        ).fetchone()
        return _embedding_from_row(row) if row else None

    def embeddings_for(self, model_id: str, model_revision: str) -> list[EmbeddingRecord]:
        rows = self._connection.execute(
            """
            SELECT * FROM semantic_embeddings
            WHERE model_id = ? AND model_revision = ?
            ORDER BY platform, clip_id
            """,
            (model_id, model_revision),
        ).fetchall()
        return [_embedding_from_row(row) for row in rows]

    def store_embeddings(self, records: list[EmbeddingRecord]) -> None:
        """Atomically store one completed batch (never half a batch)."""
        if not records:
            return
        values = [
            (
                record.platform,
                record.clip_id,
                record.model_id,
                record.model_revision,
                record.input_hash,
                record.dimension,
                record.vector,
                record.generated_at,
            )
            for record in records
        ]
        with self._lock, self._connection:
            self._connection.executemany(
                """
                INSERT INTO semantic_embeddings (
                    platform, clip_id, model_id, model_revision, input_hash,
                    dimension, vector, generated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(platform, clip_id, model_id, model_revision) DO UPDATE SET
                    input_hash = excluded.input_hash,
                    dimension = excluded.dimension,
                    vector = excluded.vector,
                    generated_at = excluded.generated_at
                """,
                values,
            )

    def delete_embedding(
        self, platform: str, clip_id: str, model_id: str, model_revision: str
    ) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                DELETE FROM semantic_embeddings
                WHERE platform = ? AND clip_id = ? AND model_id = ? AND model_revision = ?
                """,
                (platform, clip_id, model_id, model_revision),
            )

    def topic_assignments(
        self, platform: str | None = None, clip_id: str | None = None
    ) -> list[TopicAssignment]:
        sql = "SELECT * FROM topic_assignments"
        values: tuple[str, ...] = ()
        if platform is not None and clip_id is not None:
            sql += " WHERE platform = ? AND clip_id = ?"
            values = (platform, clip_id)
        sql += " ORDER BY platform, clip_id, provenance DESC, confidence DESC, topic"
        rows = self._connection.execute(sql, values).fetchall()
        return [_topic_from_row(row) for row in rows]

    def topic_names(self, platform: str, clip_id: str) -> tuple[str, ...]:
        assignments = self.topic_assignments(platform, clip_id)
        manual = {item.topic for item in assignments if item.provenance == "manual"}
        generated = {item.topic for item in assignments if item.provenance == "model"}
        return tuple(sorted(manual | generated))

    def replace_model_topics(
        self, platform: str, clip_id: str, assignments: list[TopicAssignment]
    ) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "DELETE FROM topic_assignments "
                "WHERE platform = ? AND clip_id = ? AND provenance = 'model'",
                (platform, clip_id),
            )
            self._connection.executemany(
                """
                INSERT INTO topic_assignments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.platform,
                        item.clip_id,
                        item.topic,
                        item.confidence,
                        item.provenance,
                        item.model_id,
                        item.model_revision,
                        item.definition_hash,
                        item.input_hash,
                        item.threshold,
                        item.generated_at,
                    )
                    for item in assignments
                ],
            )

    def set_manual_topic(self, platform: str, clip_id: str, topic: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO topic_assignments VALUES (?, ?, ?, 1.0, 'manual',
                    NULL, NULL, NULL, NULL, NULL, ?)
                ON CONFLICT(platform, clip_id, topic, provenance) DO UPDATE SET
                    confidence = 1.0, generated_at = excluded.generated_at
                """,
                (platform, clip_id, topic, now),
            )

    def remove_manual_topic(self, platform: str, clip_id: str, topic: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "DELETE FROM topic_assignments WHERE platform = ? AND clip_id = ? "
                "AND topic = ? AND provenance = 'manual'",
                (platform, clip_id, topic),
            )

    def remove_topic(self, topic: str) -> None:
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM topic_assignments WHERE topic = ?", (topic,))

    def set_transcript(
        self,
        platform: str,
        clip_id: str,
        *,
        text: str | None,
        language: str | None,
        model_id: str,
        model_revision: str,
        source_hash: str,
        processing_seconds: float,
        status: str,
        error: str | None = None,
    ) -> None:
        with self._lock, self._connection:
            previous = self._connection.execute(
                "SELECT transcript_text FROM clips WHERE platform = ? AND clip_id = ?",
                (platform, clip_id),
            ).fetchone()
            if previous is None:
                raise CatalogError(f"clip id not found for transcript: {clip_id}")
            cursor = self._connection.execute(
                """
                UPDATE clips SET transcript_text = ?, transcript_language = ?,
                    transcript_model_id = ?, transcript_model_revision = ?,
                    transcript_source_hash = ?, transcript_processing_seconds = ?,
                    transcript_status = ?, transcript_error = ?, transcript_updated_at = ?
                WHERE platform = ? AND clip_id = ?
                """,
                (
                    text,
                    language,
                    model_id,
                    model_revision,
                    source_hash,
                    processing_seconds,
                    status,
                    error,
                    datetime.now(timezone.utc).isoformat(),
                    platform,
                    clip_id,
                ),
            )
            if previous["transcript_text"] != text:
                self._invalidate_generated(platform, clip_id)
        if cursor.rowcount != 1:  # Defensive: the row is selected under the same write lock.
            raise CatalogError(f"clip id not found for transcript: {clip_id}")

    def set_visible_text(
        self,
        platform: str,
        clip_id: str,
        *,
        text: str | None,
        segments: tuple[VisibleTextSegment, ...],
        confidence: float | None,
        model_id: str,
        model_revision: str,
        source_hash: str,
        sample_policy: str,
        processing_seconds: float,
        status: str,
        error: str | None = None,
    ) -> None:
        """Store one terminal OCR result and invalidate only changed derived data."""
        serialized = json.dumps(
            [
                {
                    "timestamp_seconds": item.timestamp_seconds,
                    "text": item.text,
                    "confidence": item.confidence,
                }
                for item in segments
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        with self._lock, self._connection:
            previous = self._connection.execute(
                "SELECT visible_text FROM clips WHERE platform = ? AND clip_id = ?",
                (platform, clip_id),
            ).fetchone()
            if previous is None:
                raise CatalogError(f"clip id not found for visible text: {clip_id}")
            cursor = self._connection.execute(
                """
                UPDATE clips SET visible_text = ?, visible_text_segments_json = ?,
                    visible_text_confidence = ?, visible_text_model_id = ?,
                    visible_text_model_revision = ?, visible_text_source_hash = ?,
                    visible_text_sample_policy = ?, visible_text_processing_seconds = ?,
                    visible_text_status = ?, visible_text_error = ?,
                    visible_text_updated_at = ?
                WHERE platform = ? AND clip_id = ?
                """,
                (
                    text,
                    serialized,
                    confidence,
                    model_id,
                    model_revision,
                    source_hash,
                    sample_policy,
                    processing_seconds,
                    status,
                    error,
                    datetime.now(timezone.utc).isoformat(),
                    platform,
                    clip_id,
                ),
            )
            if previous["visible_text"] != text:
                self._invalidate_generated(platform, clip_id)
        if cursor.rowcount != 1:
            raise CatalogError(f"clip id not found for visible text: {clip_id}")

    def comments_for(self, platform: str, clip_id: str) -> list[CatalogComment]:
        rows = self._connection.execute(
            "SELECT * FROM clip_comments WHERE platform = ? AND clip_id = ? "
            "ORDER BY rowid",
            (platform, clip_id),
        ).fetchall()
        return [
            CatalogComment(
                row["platform"],
                row["clip_id"],
                row["comment_id"],
                row["text"],
                row["retrieved_at"],
            )
            for row in rows
        ]

    def set_comments(
        self,
        platform: str,
        clip_id: str,
        comments: list[tuple[str, str]],
        *,
        status: str,
        error: str | None = None,
    ) -> None:
        """Replace one clip's minimal comments and invalidate changed generated data."""
        retrieved_at = datetime.now(timezone.utc).isoformat()
        text = "\n".join(item_text for _, item_text in comments) or None
        with self._lock, self._connection:
            previous = self._connection.execute(
                "SELECT comment_text FROM clips WHERE platform = ? AND clip_id = ?",
                (platform, clip_id),
            ).fetchone()
            if previous is None:
                raise CatalogError(f"clip id not found for comments: {clip_id}")
            self._connection.execute(
                "DELETE FROM clip_comments WHERE platform = ? AND clip_id = ?",
                (platform, clip_id),
            )
            self._connection.executemany(
                "INSERT INTO clip_comments VALUES (?, ?, ?, ?, ?)",
                [
                    (platform, clip_id, comment_id, item_text, retrieved_at)
                    for comment_id, item_text in comments
                ],
            )
            self._connection.execute(
                "UPDATE clips SET comment_text = ?, comment_status = ?, "
                "comment_retrieved_at = ?, comment_error = ? "
                "WHERE platform = ? AND clip_id = ?",
                (text, status, retrieved_at, error, platform, clip_id),
            )
            if previous["comment_text"] != text:
                self._invalidate_generated(platform, clip_id)

    def set_comment_status(
        self,
        platform: str,
        clip_id: str,
        status: str,
        error: str | None = None,
    ) -> None:
        """Record a retryable outcome without discarding previously retained comments."""
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "UPDATE clips SET comment_status = ?, comment_error = ? "
                "WHERE platform = ? AND clip_id = ?",
                (status, error, platform, clip_id),
            )
        if cursor.rowcount != 1:
            raise CatalogError(f"clip id not found for comments: {clip_id}")

    def purge_comments(self) -> int:
        """Remove all comment enrichment and invalidate only affected generated data."""
        with self._lock, self._connection:
            rows = self._connection.execute(
                "SELECT platform, clip_id, comment_text FROM clips "
                "WHERE comment_status IS NOT NULL OR comment_text IS NOT NULL"
            ).fetchall()
            self._connection.execute("DELETE FROM clip_comments")
            self._connection.execute(
                "UPDATE clips SET comment_text = NULL, comment_status = NULL, "
                "comment_retrieved_at = NULL, comment_error = NULL"
            )
            for row in rows:
                if row["comment_text"] is not None:
                    self._invalidate_generated(row["platform"], row["clip_id"])
        return len(rows)

    def _invalidate_generated(self, platform: str, clip_id: str) -> None:
        """Delete derived data while the caller holds the catalog write lock."""
        self._connection.execute(
            "DELETE FROM semantic_embeddings WHERE platform = ? AND clip_id = ?",
            (platform, clip_id),
        )
        self._connection.execute(
            "DELETE FROM topic_assignments "
            "WHERE platform = ? AND clip_id = ? AND provenance = 'model'",
            (platform, clip_id),
        )

    def get_media_signature(self, platform: str, clip_id: str) -> MediaSignature | None:
        row = self._connection.execute(
            "SELECT * FROM media_signatures WHERE platform = ? AND clip_id = ?",
            (platform, clip_id),
        ).fetchone()
        if row is None:
            return None
        return MediaSignature(
            platform=row["platform"],
            clip_id=row["clip_id"],
            file_hash=row["file_hash"],
            file_size=row["file_size"],
            file_mtime_ns=row["file_mtime_ns"],
            algorithm_version=row["algorithm_version"],
            duration_seconds=row["duration_seconds"],
            frame_hashes=tuple(json.loads(row["frame_hashes_json"])),
            status=row["status"],
            error=row["error"],
            generated_at=row["generated_at"],
        )

    def store_media_signature(self, signature: MediaSignature) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO media_signatures VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(platform, clip_id) DO UPDATE SET
                    file_hash = excluded.file_hash,
                    file_size = excluded.file_size,
                    file_mtime_ns = excluded.file_mtime_ns,
                    algorithm_version = excluded.algorithm_version,
                    duration_seconds = excluded.duration_seconds,
                    frame_hashes_json = excluded.frame_hashes_json,
                    status = excluded.status,
                    error = excluded.error,
                    generated_at = excluded.generated_at
                """,
                (
                    signature.platform,
                    signature.clip_id,
                    signature.file_hash,
                    signature.file_size,
                    signature.file_mtime_ns,
                    signature.algorithm_version,
                    signature.duration_seconds,
                    json.dumps(signature.frame_hashes),
                    signature.status,
                    signature.error,
                    signature.generated_at,
                ),
            )


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
    visible_segments = tuple(
        VisibleTextSegment(
            float(item["timestamp_seconds"]),
            str(item["text"]),
            float(item["confidence"]),
        )
        for item in json.loads(row["visible_text_segments_json"])
    )
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
        transcript_text=row["transcript_text"],
        transcript_language=row["transcript_language"],
        transcript_model_id=row["transcript_model_id"],
        transcript_model_revision=row["transcript_model_revision"],
        transcript_source_hash=row["transcript_source_hash"],
        transcript_processing_seconds=row["transcript_processing_seconds"],
        transcript_status=row["transcript_status"],
        transcript_error=row["transcript_error"],
        transcript_updated_at=row["transcript_updated_at"],
        comment_text=row["comment_text"],
        comment_status=row["comment_status"],
        comment_retrieved_at=row["comment_retrieved_at"],
        comment_error=row["comment_error"],
        visible_text=row["visible_text"],
        visible_text_segments=visible_segments,
        visible_text_confidence=row["visible_text_confidence"],
        visible_text_model_id=row["visible_text_model_id"],
        visible_text_model_revision=row["visible_text_model_revision"],
        visible_text_source_hash=row["visible_text_source_hash"],
        visible_text_sample_policy=row["visible_text_sample_policy"],
        visible_text_processing_seconds=row["visible_text_processing_seconds"],
        visible_text_status=row["visible_text_status"],
        visible_text_error=row["visible_text_error"],
        visible_text_updated_at=row["visible_text_updated_at"],
    )


def _embedding_from_row(row: sqlite3.Row) -> EmbeddingRecord:
    return EmbeddingRecord(
        platform=row["platform"],
        clip_id=row["clip_id"],
        model_id=row["model_id"],
        model_revision=row["model_revision"],
        input_hash=row["input_hash"],
        dimension=row["dimension"],
        vector=row["vector"],
        generated_at=row["generated_at"],
    )


def _topic_from_row(row: sqlite3.Row) -> TopicAssignment:
    return TopicAssignment(
        platform=row["platform"],
        clip_id=row["clip_id"],
        topic=row["topic"],
        confidence=row["confidence"],
        provenance=row["provenance"],
        model_id=row["model_id"],
        model_revision=row["model_revision"],
        definition_hash=row["definition_hash"],
        input_hash=row["input_hash"],
        threshold=row["threshold"],
        generated_at=row["generated_at"],
    )
