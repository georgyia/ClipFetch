"""Device-local application-state database for ClipFetch Watch.

This is deliberately separate from the portable per-library ``catalog.sqlite3``. It holds
device/user interaction state that must **not** travel with a copied library: the registry of known
libraries, playback progress, favorites, and the download job queue. It is versioned independently
via its own forward-only migrations, mirroring :mod:`clipfetch.catalog`.

``root_path`` values are stored for local resolution but are private: API responses expose library
IDs and display names, never paths (ADR 0001, boundary rule 5).
"""

from __future__ import annotations

import os
import sqlite3
import sys
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

APP_DIR_NAME = "clipfetch"
APP_STATE_NAME = "appstate.sqlite3"
CURRENT_SCHEMA_VERSION = 2

Migration = Callable[[sqlite3.Connection], None]


class AppStateError(RuntimeError):
    """The application-state database is invalid or cannot be opened."""


@dataclass(frozen=True)
class LibraryEntry:
    id: str
    display_name: str
    root_path: str
    last_opened_at: str | None
    last_health: str | None
    created_at: str


@dataclass(frozen=True)
class PlaybackEntry:
    library_id: str
    clip_id: str
    position_ms: int
    duration_ms: int | None
    completed: bool
    play_count: int
    last_played_at: str
    updated_at: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _migration_1(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE app_libraries (
            id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            root_path TEXT NOT NULL UNIQUE,
            last_opened_at TEXT,
            last_health TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE playback_state (
            library_id TEXT NOT NULL,
            clip_id TEXT NOT NULL,
            position_ms INTEGER NOT NULL DEFAULT 0,
            duration_ms INTEGER,
            completed INTEGER NOT NULL DEFAULT 0,
            play_count INTEGER NOT NULL DEFAULT 0,
            last_played_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (library_id, clip_id)
        )
        """
    )
    connection.execute(
        "CREATE INDEX playback_recent_idx ON playback_state(library_id, last_played_at)"
    )
    connection.execute(
        """
        CREATE TABLE favorites (
            library_id TEXT NOT NULL,
            clip_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (library_id, clip_id)
        )
        """
    )


def _migration_2(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE jobs (
            id TEXT PRIMARY KEY,
            library_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            state TEXT NOT NULL,
            source_permalink TEXT,
            request_json TEXT NOT NULL,
            result_json TEXT,
            public_error_code TEXT,
            public_error_message TEXT,
            attempt INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3,
            progress_current INTEGER,
            progress_total INTEGER,
            phase TEXT,
            cancel_requested INTEGER NOT NULL DEFAULT 0,
            lease_owner TEXT,
            lease_expires_at TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute("CREATE INDEX jobs_state_idx ON jobs(state, created_at)")
    connection.execute("CREATE INDEX jobs_lease_idx ON jobs(lease_expires_at)")
    connection.execute(
        """
        CREATE TABLE job_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            phase TEXT,
            message TEXT,
            progress_current INTEGER,
            progress_total INTEGER,
            created_at TEXT NOT NULL,
            UNIQUE (job_id, sequence)
        )
        """
    )


MIGRATIONS: dict[int, Migration] = {1: _migration_1, 2: _migration_2}


def default_appstate_path() -> Path:
    """Return the OS-appropriate default location for the application-state database."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / APP_DIR_NAME / APP_STATE_NAME


def _migrate(connection: sqlite3.Connection) -> None:
    """Apply forward-only migrations atomically."""
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
        row = connection.execute("SELECT version FROM schema_version").fetchone()
        version = int(row[0]) if row else 0
        if version > CURRENT_SCHEMA_VERSION:
            raise AppStateError(
                f"app-state schema {version} is newer than supported {CURRENT_SCHEMA_VERSION}"
            )
        for target in range(version + 1, CURRENT_SCHEMA_VERSION + 1):
            MIGRATIONS[target](connection)
            if row:
                connection.execute("UPDATE schema_version SET version = ?", (target,))
            else:
                connection.execute("INSERT INTO schema_version(version) VALUES (?)", (target,))
                row = (target,)
        connection.commit()
    except Exception:
        connection.rollback()
        raise


class AppState:
    """Repository around the device-local application-state database."""

    def __init__(self, path: Path, connection: sqlite3.Connection) -> None:
        self.path = path
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.Lock()

    @classmethod
    def open(cls, path: Path | None = None) -> AppState:
        resolved = (path or default_appstate_path()).resolve()
        connection: sqlite3.Connection | None = None
        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(resolved, timeout=10, check_same_thread=False)
            connection.execute("PRAGMA foreign_keys = ON")
            _migrate(connection)
        except (OSError, sqlite3.Error) as err:
            if connection is not None:
                connection.close()
            raise AppStateError(f"cannot open app state at {resolved}: {err}") from err
        return cls(resolved, connection)

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> AppState:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def schema_version(self) -> int:
        row = self._connection.execute("SELECT version FROM schema_version").fetchone()
        return int(row[0])

    # -- library registry ------------------------------------------------------

    def register_library(self, display_name: str, root_path: Path) -> LibraryEntry:
        """Register a library by path, or return the existing entry for that path."""
        normalized = str(root_path.resolve())
        with self._lock:
            existing = self._connection.execute(
                "SELECT * FROM app_libraries WHERE root_path = ?", (normalized,)
            ).fetchone()
            if existing is not None:
                return _library(existing)
            entry = LibraryEntry(
                id=uuid.uuid4().hex,
                display_name=display_name,
                root_path=normalized,
                last_opened_at=None,
                last_health=None,
                created_at=_now(),
            )
            self._connection.execute(
                "INSERT INTO app_libraries"
                "(id, display_name, root_path, last_opened_at, last_health, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    entry.id,
                    entry.display_name,
                    entry.root_path,
                    entry.last_opened_at,
                    entry.last_health,
                    entry.created_at,
                ),
            )
            self._connection.commit()
            return entry

    def list_libraries(self) -> tuple[LibraryEntry, ...]:
        rows = self._connection.execute(
            "SELECT * FROM app_libraries ORDER BY created_at, id"
        ).fetchall()
        return tuple(_library(row) for row in rows)

    def get_library(self, library_id: str) -> LibraryEntry:
        row = self._connection.execute(
            "SELECT * FROM app_libraries WHERE id = ?", (library_id,)
        ).fetchone()
        if row is None:
            raise AppStateError(f"unknown library: {library_id}")
        return _library(row)

    def activate_library(self, library_id: str) -> LibraryEntry:
        """Mark a library as most-recently opened and return it."""
        with self._lock:
            entry = self.get_library(library_id)
            self._connection.execute(
                "UPDATE app_libraries SET last_opened_at = ? WHERE id = ?", (_now(), library_id)
            )
            self._connection.commit()
        return self.get_library(entry.id)

    def last_opened_library(self) -> LibraryEntry | None:
        row = self._connection.execute(
            "SELECT * FROM app_libraries WHERE last_opened_at IS NOT NULL "
            "ORDER BY last_opened_at DESC LIMIT 1"
        ).fetchone()
        return _library(row) if row is not None else None

    def set_library_health(self, library_id: str, health: str) -> None:
        with self._lock:
            self._connection.execute(
                "UPDATE app_libraries SET last_health = ? WHERE id = ?", (health, library_id)
            )
            self._connection.commit()

    def unregister_library(self, library_id: str) -> None:
        """Remove a library and its device state. Never touches the library's files or catalog."""
        with self._lock:
            cursor = self._connection.execute(
                "DELETE FROM app_libraries WHERE id = ?", (library_id,)
            )
            if cursor.rowcount == 0:
                raise AppStateError(f"unknown library: {library_id}")
            self._connection.execute(
                "DELETE FROM playback_state WHERE library_id = ?", (library_id,)
            )
            self._connection.execute(
                "DELETE FROM favorites WHERE library_id = ?", (library_id,)
            )
            self._connection.commit()

    # -- playback --------------------------------------------------------------

    def get_playback(self, library_id: str, clip_id: str) -> PlaybackEntry | None:
        row = self._connection.execute(
            "SELECT * FROM playback_state WHERE library_id = ? AND clip_id = ?",
            (library_id, clip_id),
        ).fetchone()
        return _playback(row) if row is not None else None

    def upsert_playback(
        self,
        library_id: str,
        clip_id: str,
        *,
        position_ms: int,
        duration_ms: int | None = None,
        completed: bool = False,
    ) -> PlaybackEntry:
        """Record the newest absolute playback position for a clip (idempotent)."""
        if position_ms < 0:
            raise AppStateError("position_ms must be non-negative")
        now = _now()
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO playback_state
                    (library_id, clip_id, position_ms, duration_ms, completed,
                     play_count, last_played_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(library_id, clip_id) DO UPDATE SET
                    position_ms = excluded.position_ms,
                    duration_ms = COALESCE(excluded.duration_ms, playback_state.duration_ms),
                    completed = excluded.completed,
                    play_count = playback_state.play_count + 1,
                    last_played_at = excluded.last_played_at,
                    updated_at = excluded.updated_at
                """,
                (library_id, clip_id, position_ms, duration_ms, int(completed), now, now),
            )
            self._connection.commit()
        entry = self.get_playback(library_id, clip_id)
        assert entry is not None
        return entry

    def recent_playback(self, library_id: str, *, limit: int = 24) -> tuple[PlaybackEntry, ...]:
        rows = self._connection.execute(
            "SELECT * FROM playback_state WHERE library_id = ? "
            "ORDER BY last_played_at DESC, clip_id LIMIT ?",
            (library_id, max(1, limit)),
        ).fetchall()
        return tuple(_playback(row) for row in rows)

    # -- favorites -------------------------------------------------------------

    def add_favorite(self, library_id: str, clip_id: str) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT OR IGNORE INTO favorites(library_id, clip_id, created_at) VALUES (?, ?, ?)",
                (library_id, clip_id, _now()),
            )
            self._connection.commit()

    def remove_favorite(self, library_id: str, clip_id: str) -> None:
        with self._lock:
            self._connection.execute(
                "DELETE FROM favorites WHERE library_id = ? AND clip_id = ?", (library_id, clip_id)
            )
            self._connection.commit()

    def is_favorite(self, library_id: str, clip_id: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM favorites WHERE library_id = ? AND clip_id = ?", (library_id, clip_id)
        ).fetchone()
        return row is not None

    def list_favorites(self, library_id: str) -> tuple[str, ...]:
        rows = self._connection.execute(
            "SELECT clip_id FROM favorites WHERE library_id = ? ORDER BY created_at DESC, clip_id",
            (library_id,),
        ).fetchall()
        return tuple(row["clip_id"] for row in rows)


def _library(row: sqlite3.Row) -> LibraryEntry:
    return LibraryEntry(
        id=row["id"],
        display_name=row["display_name"],
        root_path=row["root_path"],
        last_opened_at=row["last_opened_at"],
        last_health=row["last_health"],
        created_at=row["created_at"],
    )


def _playback(row: sqlite3.Row) -> PlaybackEntry:
    return PlaybackEntry(
        library_id=row["library_id"],
        clip_id=row["clip_id"],
        position_ms=row["position_ms"],
        duration_ms=row["duration_ms"],
        completed=bool(row["completed"]),
        play_count=row["play_count"],
        last_played_at=row["last_played_at"],
        updated_at=row["updated_at"],
    )
