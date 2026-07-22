"""Favorites service.

Wraps the device-local :class:`~clipfetch.appstate.AppState` favorites table, and resolves favorite
ids to public :class:`~clipfetch.contracts.ClipSummary` values via the catalog. Favorites are per
active library and never leave the device beyond the clip summaries the API already exposes.
"""

from __future__ import annotations

from pathlib import Path

from clipfetch.appstate import AppState
from clipfetch.catalog import CatalogError
from clipfetch.contracts import ClipPage, ClipSummary
from clipfetch.services import catalog_service


def is_favorite(appstate: AppState, library_id: str, clip_id: str) -> bool:
    return appstate.is_favorite(library_id, clip_id)


def set_favorite(appstate: AppState, library_id: str, clip_id: str, favorite: bool) -> bool:
    """Add or remove a favorite (idempotent) and return the resulting state."""
    if favorite:
        appstate.add_favorite(library_id, clip_id)
    else:
        appstate.remove_favorite(library_id, clip_id)
    return favorite


def list_favorites(root: Path, appstate: AppState, library_id: str) -> ClipPage:
    """Return favorited clips as summaries, newest first, skipping any whose record is gone."""
    summaries: list[ClipSummary] = []
    for clip_id in appstate.list_favorites(library_id):
        try:
            summaries.append(catalog_service.get_clip(root, clip_id).summary)
        except CatalogError:
            continue
    return ClipPage(items=tuple(summaries), next_cursor=None, total_matched=len(summaries))
