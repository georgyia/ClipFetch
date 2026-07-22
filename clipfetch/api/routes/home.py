"""Home endpoints: the composed rail list, and per-rail lazy pagination.

FastAPI evaluates these route signatures at runtime, so this module intentionally does not use
``from __future__ import annotations`` and uses ``Optional[...]`` for Python 3.9 compatibility.
"""

from pathlib import Path
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Query

from clipfetch.api.dependencies import ActiveLibraryDep, AppStateDep
from clipfetch.api.errors import ApiException
from clipfetch.collections import CollectionError
from clipfetch.services import home_service
from clipfetch.services.catalog_service import InvalidCursorError
from clipfetch.topics import TopicError

router = APIRouter(prefix="/api/v1", tags=["home"])


@router.get("/home")
def home(appstate: AppStateDep, library: ActiveLibraryDep) -> dict[str, Any]:
    rails = home_service.build_home(Path(library.root_path), appstate, library.id)
    return {"rails": [rail.to_dict() for rail in rails]}


@router.get("/rails/{rail_id}")
def rail(
    rail_id: str,
    appstate: AppStateDep,
    library: ActiveLibraryDep,
    cursor: Annotated[Optional[str], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 12,
) -> dict[str, Any]:
    try:
        page = home_service.rail_page(
            Path(library.root_path), appstate, library.id, rail_id, cursor=cursor, limit=limit
        )
    except KeyError as err:
        raise ApiException(404, "rail_not_found", f"unknown rail: {rail_id}") from err
    except InvalidCursorError as err:
        raise ApiException(422, "invalid_cursor", str(err)) from err
    except (TopicError, CollectionError) as err:
        raise ApiException(404, "rail_not_found", str(err)) from err
    return page.to_dict()
