"""Media delivery endpoints, addressed only by clip ID.

The poster endpoint returns a cached neutral placeholder until real posters are generated. The
server resolves the clip through the active library catalog and never accepts a path parameter.
"""

from fastapi import APIRouter, Request, Response

from clipfetch.api.dependencies import ActiveLibraryRootDep
from clipfetch.api.errors import ApiException
from clipfetch.catalog import CatalogError
from clipfetch.library import find_clip
from clipfetch.services import media_service

router = APIRouter(prefix="/api/v1/clips", tags=["media"])


@router.get("/{clip_id}/poster")
def get_poster(clip_id: str, root: ActiveLibraryRootDep, request: Request) -> Response:
    try:
        record = find_clip(root, clip_id)
    except CatalogError as err:
        raise ApiException(404, "clip_not_found", str(err)) from err

    etag = media_service.poster_etag(record)
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})

    return Response(
        content=media_service.poster_placeholder(record),
        media_type="image/svg+xml",
        headers={"ETag": etag, "Cache-Control": "public, max-age=3600"},
    )
