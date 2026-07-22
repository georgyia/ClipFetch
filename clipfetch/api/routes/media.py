"""Media delivery endpoints, addressed only by clip ID.

The poster endpoint returns a cached neutral placeholder until real posters are generated. The
server resolves the clip through the active library catalog and never accepts a path parameter.
"""

from pathlib import Path

from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

from clipfetch.api.dependencies import ActiveLibraryRootDep
from clipfetch.api.errors import ApiException
from clipfetch.catalog import CatalogError
from clipfetch.library import find_clip
from clipfetch.services import media_service
from clipfetch.services.media_service import MediaError

router = APIRouter(prefix="/api/v1/clips", tags=["media"])


def _resolve_media(clip_id: str, root: Path) -> Path:
    try:
        record = find_clip(root, clip_id)
    except CatalogError as err:
        raise ApiException(404, "clip_not_found", str(err)) from err
    try:
        path = media_service.safe_media_path(root, record.relative_path)
    except MediaError as err:
        raise ApiException(
            404, "media_unavailable", "The media file could not be resolved."
        ) from err
    if not path.is_file():
        raise ApiException(
            404,
            "media_unavailable",
            "The local media file could not be found.",
            recovery_actions=("locate_file", "retry_download"),
        )
    return path


def _base_headers(path: Path, etag: str) -> dict[str, str]:
    return {
        "Accept-Ranges": "bytes",
        "ETag": etag,
        "Content-Type": media_service.media_type_for(path),
    }


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


@router.head("/{clip_id}/media")
def head_media(clip_id: str, root: ActiveLibraryRootDep) -> Response:
    path = _resolve_media(clip_id, root)
    stat = path.stat()
    etag = media_service.media_etag(stat.st_size, stat.st_mtime_ns)
    headers = _base_headers(path, etag)
    headers["Content-Length"] = str(stat.st_size)
    return Response(status_code=200, headers=headers)


@router.get("/{clip_id}/media")
def get_media(clip_id: str, root: ActiveLibraryRootDep, request: Request) -> Response:
    path = _resolve_media(clip_id, root)
    stat = path.stat()
    size = stat.st_size
    etag = media_service.media_etag(stat.st_size, stat.st_mtime_ns)

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag, "Accept-Ranges": "bytes"})

    range_header = request.headers.get("range")
    if range_header is None:
        headers = _base_headers(path, etag)
        headers["Content-Length"] = str(size)
        return StreamingResponse(
            media_service.file_iterator(path, 0, size - 1),
            status_code=200,
            headers=headers,
            media_type=media_service.media_type_for(path),
        )

    parsed = media_service.parse_byte_range(range_header, size)
    if parsed is None:
        return Response(
            status_code=416,
            headers={"Content-Range": f"bytes */{size}", "Accept-Ranges": "bytes"},
        )

    start, end = parsed
    headers = _base_headers(path, etag)
    headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    headers["Content-Length"] = str(end - start + 1)
    return StreamingResponse(
        media_service.file_iterator(path, start, end),
        status_code=206,
        headers=headers,
        media_type=media_service.media_type_for(path),
    )
