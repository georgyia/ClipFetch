"""Diagnostics endpoint: a redacted support bundle.

Unlike most endpoints this does not require an active library — it is meant to work even when the
app is in a broken state, which is exactly when a support bundle is useful.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from clipfetch.api.dependencies import AppStateDep
from clipfetch.services import diagnostics_service

router = APIRouter(prefix="/api/v1", tags=["diagnostics"])


@router.get("/diagnostics")
def diagnostics(appstate: AppStateDep) -> dict[str, Any]:
    return diagnostics_service.build_bundle(appstate)
