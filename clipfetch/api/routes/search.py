"""Search endpoint: text search now, with a semantic-capability signal and graceful fallback.

FastAPI evaluates these route signatures at runtime, so this module intentionally does not use
``from __future__ import annotations`` and uses ``Optional[...]`` for Python 3.9 compatibility.
"""

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Query

from clipfetch.api.dependencies import ActiveLibraryRootDep
from clipfetch.api.errors import ApiException
from clipfetch.services import search_service
from clipfetch.services.catalog_service import InvalidCursorError
from clipfetch.services.search_service import SEARCH_MODES

router = APIRouter(prefix="/api/v1", tags=["search"])


@router.get("/search")
def search(
    root: ActiveLibraryRootDep,
    q: Annotated[str, Query(min_length=1)],
    mode: Annotated[str, Query()] = "all",
    cursor: Annotated[Optional[str], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 24,
) -> dict[str, Any]:
    if mode not in SEARCH_MODES:
        raise ApiException(422, "invalid_mode", f"mode must be one of: {', '.join(SEARCH_MODES)}")
    try:
        result = search_service.search(root, q, mode=mode, cursor=cursor, limit=limit)
    except InvalidCursorError as err:
        raise ApiException(422, "invalid_cursor", str(err)) from err

    payload: dict[str, Any] = {"query": q, "requested_mode": mode}
    payload.update(result.to_dict())
    return payload
