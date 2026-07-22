from __future__ import annotations

from pathlib import Path

import pytest

from clipfetch.catalog import CatalogRecord
from clipfetch.services import media_service
from clipfetch.services.media_service import MediaError


def _record(clip_id: str = "ABC", relative_path: str = "instagram/ABC.mp4") -> CatalogRecord:
    return CatalogRecord(
        platform="instagram",
        clip_id=clip_id,
        relative_path=relative_path,
        file_size=10,
        file_mtime_ns=20,
        downloaded_at="2026-01-01T00:00:00+00:00",
        source_url=None,
        author="creator",
        caption="hi",
        likes=1,
        metadata_state="sidecar-v2",
    )


@pytest.mark.parametrize(
    ("header", "size", "expected"),
    [
        ("bytes=0-99", 1000, (0, 99)),
        ("bytes=100-", 1000, (100, 999)),
        ("bytes=-50", 1000, (950, 999)),
        ("bytes=0-100000", 1000, (0, 999)),  # end clamped to last byte
        ("bytes=1000-", 1000, None),  # start past end
        ("bytes=-0", 1000, None),  # zero-length suffix
        ("bytes=abc", 1000, None),
        ("bytes=0-10,20-30", 1000, None),  # multi-range unsupported
        ("chunks=0-10", 1000, None),  # wrong unit
        ("bytes=0-0", 1, (0, 0)),
        ("bytes=0-0", 0, None),  # empty file
    ],
)
def test_parse_byte_range(header, size, expected):
    assert media_service.parse_byte_range(header, size) == expected


def test_file_iterator_reads_inclusive_range(tmp_path):
    path = tmp_path / "clip.bin"
    path.write_bytes(bytes(range(256)))
    chunks = b"".join(media_service.file_iterator(path, 10, 19, chunk=4))
    assert chunks == bytes(range(10, 20))


def test_media_type_and_etag():
    assert media_service.media_type_for(Path("a.mp4")) == "video/mp4"
    assert media_service.media_type_for(Path("a.webm")) == "video/webm"
    assert media_service.media_type_for(Path("a.txt")) == "application/octet-stream"
    assert media_service.media_etag(255, 16) == '"ff-10"'


def test_safe_media_path_contains_within_root(tmp_path):
    (tmp_path / "instagram").mkdir()
    (tmp_path / "instagram" / "ABC.mp4").write_bytes(b"x")
    resolved = media_service.safe_media_path(tmp_path, "instagram/ABC.mp4")
    assert resolved == (tmp_path / "instagram" / "ABC.mp4").resolve()

    with pytest.raises(MediaError):
        media_service.safe_media_path(tmp_path, "../../etc/passwd")


def test_poster_placeholder_is_deterministic_svg():
    first = media_service.poster_placeholder(_record())
    assert first.startswith(b"<svg") and b"No poster available" in first
    assert first == media_service.poster_placeholder(_record())  # deterministic
    assert media_service.poster_etag(_record()) == media_service.poster_etag(_record())
