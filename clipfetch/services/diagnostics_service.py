"""Redacted diagnostics bundle for support.

Assembles a snapshot a user can safely copy into a bug report: versions, schema numbers, the
optional capability matrix, worker state, per-state job counts, the platform-support matrix, and
library *counts and health* — never a filesystem path, a library name, a source URL, a caption, or
any credential. Redaction is the point: everything here is either a version, a count, an enum, or a
capability flag.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from clipfetch import __version__
from clipfetch.api.capabilities import capability_matrix
from clipfetch.appstate import (
    JOB_CANCELLED,
    JOB_FAILED,
    JOB_QUEUED,
    JOB_RUNNING,
    JOB_SUCCEEDED,
    AppState,
)
from clipfetch.catalog import Catalog, CatalogError
from clipfetch.services import library_service

_JOB_STATES = (JOB_QUEUED, JOB_RUNNING, JOB_SUCCEEDED, JOB_FAILED, JOB_CANCELLED)


def _platform_matrix() -> list[dict[str, str]]:
    from clipfetch.platforms import ALL

    matrix = [
        {"name": platform.label, "support": "experimental" if platform.experimental else "full"}
        for platform in ALL
    ]
    # YouTube's adapter exists but is intentionally unregistered (ciphered URLs).
    matrix.append({"name": "YouTube", "support": "unavailable"})
    return matrix


def _catalog_version(appstate: AppState) -> int | None:
    root = library_service.active_library_root(appstate)
    if root is None:
        return None
    try:
        with Catalog.open(root) as catalog:
            return catalog.schema_version
    except (CatalogError, OSError):
        return None


def build_bundle(appstate: AppState) -> dict[str, Any]:
    """Build the redacted diagnostics bundle. Contains only versions, counts, enums, and flags."""
    active = library_service.active_library(appstate)
    libraries = library_service.list_libraries(appstate)
    job_states: Counter[str] = Counter()
    if active is not None:
        job_states = Counter(job.state for job in appstate.list_jobs(active.id, limit=1000))

    return {
        "app_version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema": {
            "appstate": appstate.schema_version,
            "catalog": _catalog_version(appstate),
        },
        "worker": {"state": "not_configured"},
        "capabilities": capability_matrix(),
        "platforms": _platform_matrix(),
        "libraries": {
            "count": len(libraries),
            # Health and clip count only — never the name or path.
            "active": (
                None
                if active is None
                else {"health": active.health, "clip_count": active.clip_count}
            ),
        },
        "jobs": {state: job_states.get(state, 0) for state in _JOB_STATES},
    }
