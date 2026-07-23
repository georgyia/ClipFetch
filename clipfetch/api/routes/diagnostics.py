"""Diagnostics endpoint: a redacted support bundle.

Unlike most endpoints this does not require an active library — it is meant to work even when the
app is in a broken state, which is exactly when a support bundle is useful.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from clipfetch.api.dependencies import AppStateDep
from clipfetch.services import diagnostics_service

router = APIRouter(prefix="/api/v1", tags=["diagnostics"])


@router.get("/diagnostics")
def diagnostics(request: Request, appstate: AppStateDep) -> dict[str, Any]:
    # The worker is only present when the app lifespan started one (a provider was configured).
    worker_state = "running" if getattr(request.app.state, "worker", None) is not None else (
        "configured" if getattr(request.app.state, "job_provider", None) is not None
        else "not_configured"
    )
    return diagnostics_service.build_bundle(appstate, worker_state=worker_state)
