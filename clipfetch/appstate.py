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
from datetime import datetime, timedelta, timezone
from pathlib import Path

APP_DIR_NAME = "clipfetch"
APP_STATE_NAME = "appstate.sqlite3"
CURRENT_SCHEMA_VERSION = 3

#: Job lifecycle states.
JOB_QUEUED = "queued"
JOB_RUNNING = "running"
JOB_SUCCEEDED = "succeeded"
JOB_FAILED = "failed"
JOB_CANCELLED = "cancelled"

#: Retry backoff: base seconds, doubled per attempt, capped.
_RETRY_BASE_SECONDS = 5
_RETRY_CAP_SECONDS = 300

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


@dataclass(frozen=True)
class Job:
    id: str
    library_id: str
    kind: str
    state: str
    request_json: str
    source_permalink: str | None
    result_json: str | None
    public_error_code: str | None
    public_error_message: str | None
    attempt: int
    max_attempts: int
    progress_current: int | None
    progress_total: int | None
    phase: str | None
    cancel_requested: bool
    lease_owner: str | None
    lease_expires_at: str | None
    available_at: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None
    updated_at: str


@dataclass(frozen=True)
class JobEvent:
    id: int
    job_id: str
    sequence: int
    event_type: str
    phase: str | None
    message: str | None
    progress_current: int | None
    progress_total: int | None
    created_at: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _plus_seconds(seconds: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _retry_backoff_seconds(attempt: int) -> float:
    """Exponential backoff: base * 2^(attempt-1), capped."""
    exponent = max(0, attempt - 1)
    return float(min(_RETRY_BASE_SECONDS * (2**exponent), _RETRY_CAP_SECONDS))


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


def _migration_3(connection: sqlite3.Connection) -> None:
    # A queued job (fresh or retry) is claimable only once available_at has passed; NULL means now.
    connection.execute("ALTER TABLE jobs ADD COLUMN available_at TEXT")
    connection.execute("CREATE INDEX jobs_available_idx ON jobs(state, available_at)")


MIGRATIONS: dict[int, Migration] = {
    1: _migration_1,
    2: _migration_2,
    3: _migration_3,
}


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

    # -- job queue -------------------------------------------------------------
    #
    # A single-table queue with worker leases. State machine:
    #   queued -> running -> succeeded | failed | cancelled
    # A failed job with attempts remaining returns to queued with exponential backoff
    # (available_at). Workers claim one job at a time under a lease; an expired lease is reaped back
    # to queued so a crashed worker never strands a job. Cancellation is cooperative: a flag is set,
    # honored immediately while queued and by the worker (via the returned Job) while running.

    def enqueue_job(
        self,
        library_id: str,
        kind: str,
        request_json: str,
        *,
        source_permalink: str | None = None,
        max_attempts: int = 3,
    ) -> Job:
        if max_attempts < 1:
            raise AppStateError("max_attempts must be at least 1")
        job_id = uuid.uuid4().hex
        now = _now()
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO jobs
                    (id, library_id, kind, state, source_permalink, request_json,
                     attempt, max_attempts, cancel_requested, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, 0, ?, ?)
                """,
                (job_id, library_id, kind, JOB_QUEUED, source_permalink, request_json,
                 max_attempts, now, now),
            )
            self._append_event(job_id, "enqueued", now)
            self._connection.commit()
        return self.get_job(job_id)

    def claim_job(self, owner: str, *, lease_seconds: float) -> Job | None:
        """Atomically lease the oldest available queued job to ``owner``, or return ``None``."""
        now = _now()
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._connection.execute(
                    """
                    SELECT id FROM jobs
                    WHERE state = ? AND cancel_requested = 0
                      AND (available_at IS NULL OR available_at <= ?)
                    ORDER BY created_at, id LIMIT 1
                    """,
                    (JOB_QUEUED, now),
                ).fetchone()
                if row is None:
                    self._connection.execute("ROLLBACK")
                    return None
                job_id = row["id"]
                self._connection.execute(
                    """
                    UPDATE jobs SET
                        state = ?, lease_owner = ?, lease_expires_at = ?,
                        attempt = attempt + 1, available_at = NULL,
                        started_at = COALESCE(started_at, ?), updated_at = ?
                    WHERE id = ?
                    """,
                    (JOB_RUNNING, owner, _plus_seconds(lease_seconds), now, now, job_id),
                )
                self._append_event(job_id, "claimed", now)
                self._connection.commit()
            except Exception:
                self._connection.execute("ROLLBACK")
                raise
        return self.get_job(job_id)

    def heartbeat_job(
        self,
        job_id: str,
        owner: str,
        *,
        lease_seconds: float,
        progress_current: int | None = None,
        progress_total: int | None = None,
        phase: str | None = None,
    ) -> Job:
        """Extend the lease and record progress. Returns the Job so the worker can see a cancel."""
        now = _now()
        with self._lock:
            self._require_lease(job_id, owner)
            self._connection.execute(
                """
                UPDATE jobs SET
                    lease_expires_at = ?,
                    progress_current = COALESCE(?, progress_current),
                    progress_total = COALESCE(?, progress_total),
                    phase = COALESCE(?, phase),
                    updated_at = ?
                WHERE id = ?
                """,
                (_plus_seconds(lease_seconds), progress_current, progress_total, phase, now,
                 job_id),
            )
            self._append_event(
                job_id, "progress", now, phase=phase,
                progress_current=progress_current, progress_total=progress_total,
            )
            self._connection.commit()
        return self.get_job(job_id)

    def complete_job(self, job_id: str, owner: str, *, result_json: str | None = None) -> Job:
        now = _now()
        with self._lock:
            self._require_lease(job_id, owner)
            self._connection.execute(
                """
                UPDATE jobs SET
                    state = ?, result_json = ?, lease_owner = NULL, lease_expires_at = NULL,
                    finished_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (JOB_SUCCEEDED, result_json, now, now, job_id),
            )
            self._append_event(job_id, "succeeded", now)
            self._connection.commit()
        return self.get_job(job_id)

    def fail_job(
        self, job_id: str, owner: str, *, error_code: str, error_message: str
    ) -> Job:
        """Record a failure. Retries with backoff if attempts remain and no cancel was requested."""
        now = _now()
        with self._lock:
            job = self._require_lease(job_id, owner)
            if not job.cancel_requested and job.attempt < job.max_attempts:
                self._connection.execute(
                    """
                    UPDATE jobs SET
                        state = ?, lease_owner = NULL, lease_expires_at = NULL,
                        available_at = ?, public_error_code = ?, public_error_message = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (JOB_QUEUED, _plus_seconds(_retry_backoff_seconds(job.attempt)),
                     error_code, error_message, now, job_id),
                )
                self._append_event(job_id, "retry", now, message=error_message)
            else:
                terminal = JOB_CANCELLED if job.cancel_requested else JOB_FAILED
                self._connection.execute(
                    """
                    UPDATE jobs SET
                        state = ?, lease_owner = NULL, lease_expires_at = NULL,
                        public_error_code = ?, public_error_message = ?,
                        finished_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (terminal, error_code, error_message, now, now, job_id),
                )
                self._append_event(job_id, terminal, now, message=error_message)
            self._connection.commit()
        return self.get_job(job_id)

    def cancel_job(self, job_id: str, owner: str) -> Job:
        """Finalize cancellation of a running job the worker owns (running -> cancelled)."""
        now = _now()
        with self._lock:
            self._require_lease(job_id, owner)
            self._connection.execute(
                """
                UPDATE jobs SET
                    state = ?, cancel_requested = 1, lease_owner = NULL, lease_expires_at = NULL,
                    finished_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (JOB_CANCELLED, now, now, job_id),
            )
            self._append_event(job_id, JOB_CANCELLED, now)
            self._connection.commit()
        return self.get_job(job_id)

    def request_job_cancel(self, job_id: str) -> Job:
        """Request cancellation. A queued job is cancelled at once; a running one on next check."""
        now = _now()
        with self._lock:
            job = self._get_job_locked(job_id)
            if job.state == JOB_QUEUED:
                self._connection.execute(
                    """
                    UPDATE jobs SET
                        state = ?, cancel_requested = 1, finished_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (JOB_CANCELLED, now, now, job_id),
                )
                self._append_event(job_id, JOB_CANCELLED, now)
            elif job.state == JOB_RUNNING:
                self._connection.execute(
                    "UPDATE jobs SET cancel_requested = 1, updated_at = ? WHERE id = ?",
                    (now, job_id),
                )
            self._connection.commit()
        return self.get_job(job_id)

    def reap_expired_leases(self) -> int:
        """Return expired-lease running jobs to queued for recovery. Returns the number reaped."""
        now = _now()
        with self._lock:
            rows = self._connection.execute(
                "SELECT id FROM jobs WHERE state = ? AND lease_expires_at IS NOT NULL "
                "AND lease_expires_at < ?",
                (JOB_RUNNING, now),
            ).fetchall()
            for row in rows:
                self._connection.execute(
                    """
                    UPDATE jobs SET
                        state = ?, lease_owner = NULL, lease_expires_at = NULL,
                        available_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (JOB_QUEUED, now, now, row["id"]),
                )
                self._append_event(row["id"], "lease_reaped", now)
            self._connection.commit()
            return len(rows)

    def get_job(self, job_id: str) -> Job:
        row = self._connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise AppStateError(f"unknown job: {job_id}")
        return _job(row)

    def list_jobs(self, library_id: str | None = None, *, limit: int = 50) -> tuple[Job, ...]:
        if library_id is None:
            rows = self._connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC, id LIMIT ?", (max(1, limit),)
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT * FROM jobs WHERE library_id = ? ORDER BY created_at DESC, id LIMIT ?",
                (library_id, max(1, limit)),
            ).fetchall()
        return tuple(_job(row) for row in rows)

    def list_job_events(self, job_id: str, *, after_sequence: int = 0) -> tuple[JobEvent, ...]:
        rows = self._connection.execute(
            "SELECT * FROM job_events WHERE job_id = ? AND sequence > ? ORDER BY sequence",
            (job_id, after_sequence),
        ).fetchall()
        return tuple(_job_event(row) for row in rows)

    # -- job queue internals (assume the lock is held) -------------------------

    def _get_job_locked(self, job_id: str) -> Job:
        row = self._connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise AppStateError(f"unknown job: {job_id}")
        return _job(row)

    def _require_lease(self, job_id: str, owner: str) -> Job:
        job = self._get_job_locked(job_id)
        if job.state != JOB_RUNNING:
            raise AppStateError(f"job {job_id} is not running (state: {job.state})")
        if job.lease_owner != owner:
            raise AppStateError(f"job {job_id} is not leased to {owner}")
        return job

    def _append_event(
        self,
        job_id: str,
        event_type: str,
        now: str,
        *,
        phase: str | None = None,
        message: str | None = None,
        progress_current: int | None = None,
        progress_total: int | None = None,
    ) -> None:
        row = self._connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) AS seq FROM job_events WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        self._connection.execute(
            """
            INSERT INTO job_events
                (job_id, sequence, event_type, phase, message,
                 progress_current, progress_total, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (job_id, int(row["seq"]) + 1, event_type, phase, message,
             progress_current, progress_total, now),
        )


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


def _job(row: sqlite3.Row) -> Job:
    return Job(
        id=row["id"],
        library_id=row["library_id"],
        kind=row["kind"],
        state=row["state"],
        request_json=row["request_json"],
        source_permalink=row["source_permalink"],
        result_json=row["result_json"],
        public_error_code=row["public_error_code"],
        public_error_message=row["public_error_message"],
        attempt=row["attempt"],
        max_attempts=row["max_attempts"],
        progress_current=row["progress_current"],
        progress_total=row["progress_total"],
        phase=row["phase"],
        cancel_requested=bool(row["cancel_requested"]),
        lease_owner=row["lease_owner"],
        lease_expires_at=row["lease_expires_at"],
        available_at=row["available_at"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        updated_at=row["updated_at"],
    )


def _job_event(row: sqlite3.Row) -> JobEvent:
    return JobEvent(
        id=row["id"],
        job_id=row["job_id"],
        sequence=row["sequence"],
        event_type=row["event_type"],
        phase=row["phase"],
        message=row["message"],
        progress_current=row["progress_current"],
        progress_total=row["progress_total"],
        created_at=row["created_at"],
    )
