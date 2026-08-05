"""Insights endpoint: what this library holds, and how much of it has been watched.

Read-only and computed on demand from data already stored — no new tracking, and nothing written
when the view is opened.

FastAPI evaluates these route signatures at runtime, so this module intentionally does not use
``from __future__ import annotations``.
"""

from pathlib import Path
from typing import Any

from fastapi import APIRouter

from clipfetch.api.dependencies import ActiveLibraryDep, AppStateDep
from clipfetch.api.errors import ApiException
from clipfetch.catalog import CatalogError
from clipfetch.services import insights_service

router = APIRouter(prefix="/api/v1", tags=["insights"])


@router.get("/insights")
def insights(appstate: AppStateDep, library: ActiveLibraryDep) -> dict[str, Any]:
    try:
        summary = insights_service.library_insights(
            Path(library.root_path), appstate, library.id
        )
    except CatalogError as err:
        raise ApiException(404, "library_unavailable", str(err)) from err
    return summary.to_dict()
