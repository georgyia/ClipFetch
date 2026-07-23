"""Filesystem browse endpoint for onboarding (pick a library folder).

Sandboxed to the user's home directory; returns directory names only, never file contents. See
``clipfetch.services.fs_service`` for the traversal guarantees. FastAPI evaluates these signatures
at runtime, so this module uses ``Optional[...]`` and no ``from __future__ import annotations``.
"""

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Query

from clipfetch.api.errors import ApiException
from clipfetch.services import fs_service

router = APIRouter(prefix="/api/v1/fs", tags=["fs"])


@router.get("/dirs")
def list_dirs(
    path: Annotated[Optional[str], Query(max_length=4096)] = None,
) -> dict[str, Any]:
    try:
        return fs_service.browse(path)
    except fs_service.FsError as err:
        raise ApiException(400, "invalid_path", str(err)) from err
