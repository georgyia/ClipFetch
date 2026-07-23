"""Library registry and health service.

Ties the device-local :class:`clipfetch.appstate.AppState` registry to per-library catalog health,
and produces :class:`LibrarySummary` values that expose IDs, display names, health, and counts — but
never filesystem paths (ADR 0001, boundary rule 5). The "active" library is simply the
most-recently activated one.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clipfetch.appstate import AppState, LibraryEntry
from clipfetch.catalog import CATALOG_DIR, CATALOG_NAME, Catalog, CatalogError, index_library


class LibraryServiceError(RuntimeError):
    """A library request is invalid (e.g. the path is not a readable directory)."""


@dataclass(frozen=True)
class LibrarySummary:
    id: str
    display_name: str
    last_opened_at: str | None
    health: str
    clip_count: int
    is_active: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "last_opened_at": self.last_opened_at,
            "health": self.health,
            "clip_count": self.clip_count,
            "is_active": self.is_active,
        }


def _health(root: Path) -> tuple[str, int]:
    """Return ``(health, clip_count)`` without creating a catalog that does not yet exist."""
    if not root.is_dir():
        return ("unavailable", 0)
    if not (root / CATALOG_DIR / CATALOG_NAME).exists():
        return ("uninitialized", 0)
    try:
        with Catalog.open(root) as catalog:
            return ("ready", len(catalog.all()))
    except CatalogError:
        return ("error", 0)


def _summary(entry: LibraryEntry, active_id: str | None) -> LibrarySummary:
    health, count = _health(Path(entry.root_path))
    return LibrarySummary(
        id=entry.id,
        display_name=entry.display_name,
        last_opened_at=entry.last_opened_at,
        health=health,
        clip_count=count,
        is_active=entry.id == active_id,
    )


def _active_id(appstate: AppState) -> str | None:
    active = appstate.last_opened_library()
    return active.id if active is not None else None


def register_library(appstate: AppState, display_name: str, path: str) -> LibrarySummary:
    """Register a server-readable library directory, or return the existing registration."""
    name = display_name.strip()
    if not name:
        raise LibraryServiceError("display name must not be empty")
    root = Path(path).expanduser()
    if not root.is_dir():
        raise LibraryServiceError(f"not a readable directory: {path}")
    entry = appstate.register_library(name, root)
    return _summary(entry, _active_id(appstate))


def list_libraries(appstate: AppState) -> tuple[LibrarySummary, ...]:
    active_id = _active_id(appstate)
    return tuple(_summary(entry, active_id) for entry in appstate.list_libraries())


def get_library(appstate: AppState, library_id: str) -> LibrarySummary:
    return _summary(appstate.get_library(library_id), _active_id(appstate))


def activate_library(appstate: AppState, library_id: str) -> LibrarySummary:
    entry = appstate.activate_library(library_id)
    return _summary(entry, entry.id)


def unregister_library(appstate: AppState, library_id: str) -> None:
    appstate.unregister_library(library_id)


def rescan_library(appstate: AppState, library_id: str) -> dict[str, Any]:
    """Re-index a library from disk so files added out-of-band (or by a download) appear.

    Reconciles the catalog with the media files on disk via ``index_library`` and returns the
    refreshed library summary plus a redacted scan report (counts only, no paths).
    """
    entry = appstate.get_library(library_id)
    report = index_library(Path(entry.root_path))
    summary = _summary(appstate.get_library(library_id), _active_id(appstate))
    return {
        "library": summary.to_dict(),
        "report": {
            "scanned": report.scanned,
            "inserted": report.inserted,
            "updated": report.updated,
            "unchanged": report.unchanged,
            "missing": report.missing,
        },
    }


def active_library(appstate: AppState) -> LibrarySummary | None:
    entry = appstate.last_opened_library()
    return _summary(entry, entry.id) if entry is not None else None


def active_library_root(appstate: AppState) -> Path | None:
    """Return the on-disk root of the active library, for internal media/catalog resolution only."""
    entry = appstate.last_opened_library()
    return Path(entry.root_path) if entry is not None else None
