"""The real download provider, exercised offline with injected fakes (no Playwright, no network).

Covers the orchestration, the download-to-disk ingest path, and failure-category mapping. The real
browser/collector defaults are only wired end-to-end behind the opt-in ``integration`` marker.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest

from clipfetch.appstate import JOB_FAILED, JOB_SUCCEEDED, AppState
from clipfetch.library import ClipFilter, query_library
from clipfetch.model import Clip
from clipfetch.platforms.instagram import Instagram
from clipfetch.services import ingest_service
from clipfetch.services.browser_source import BrowserSourceProvider

INSTAGRAM = Instagram()


def _clip(ident: str) -> Clip:
    return Clip(
        platform="instagram",
        ident=ident,
        video_url=f"https://cdn.example/{ident}.mp4",
        url=f"https://www.instagram.com/reel/{ident}/",
        author="creator",
        caption=f"caption {ident}",
        likes=1000,
        views=5000,
        duration_seconds=12.0,
    )


@contextmanager
def _fake_session():
    yield object()  # a stand-in BrowserContext; the fakes below never touch it


def _provider(
    clips: list[Clip], *, has_session: bool = True, download=None
) -> BrowserSourceProvider:
    def fake_download(clip: Clip, dest: Path, headers: dict) -> None:
        dest.write_bytes(f"video:{clip.ident}".encode())

    return BrowserSourceProvider(
        INSTAGRAM,
        open_session=lambda platform: _fake_session(),
        has_session=lambda ctx, platform: has_session,
        cookie_header=lambda ctx, platform: "sessionid=abc",
        harvest=lambda *a, **k: list(clips),
        download=download or fake_download,
    )


def test_downloads_and_catalogs_to_disk(tmp_path):
    root = tmp_path / "reels"
    provider = _provider([_clip("AAA"), _clip("BBB")])
    result = ingest_service.run_ingest(
        root, permalink="", count=2, quality="high", provider=provider
    )
    assert result.count == 2
    assert (root / "instagram" / "AAA.mp4").read_bytes() == b"video:AAA"
    listing = query_library(root, ClipFilter())
    assert listing.matched == 2
    ids = {clip.clip_id for clip in listing.clips}
    assert ids == {"AAA", "BBB"}


def test_missing_session_is_authentication_required(tmp_path):
    provider = _provider([_clip("AAA")], has_session=False)
    with pytest.raises(ingest_service.IngestError) as excinfo:
        list(provider.fetch("", 1, "high"))
    assert excinfo.value.code == "authentication_required"


def test_rate_limited_download_maps_to_category(tmp_path):
    def blocked(clip: Clip, dest: Path, headers: dict) -> None:
        err = OSError("blocked")
        err.status = 429  # type: ignore[attr-defined]
        raise err

    provider = _provider([_clip("AAA")], download=blocked)
    with pytest.raises(ingest_service.IngestError) as excinfo:
        list(provider.fetch("", 1, "high"))
    assert excinfo.value.code == "rate_limited"


def test_other_download_error_is_source_unavailable(tmp_path):
    def broken(clip: Clip, dest: Path, headers: dict) -> None:
        raise OSError("connection reset")

    provider = _provider([_clip("AAA")], download=broken)
    with pytest.raises(ingest_service.IngestError) as excinfo:
        list(provider.fetch("", 1, "high"))
    assert excinfo.value.code == "source_unavailable"


def test_failed_download_leaves_no_temp_file(tmp_path):
    seen: dict[str, Path] = {}

    def broken(clip: Clip, dest: Path, headers: dict) -> None:
        seen["dest"] = dest
        dest.write_bytes(b"partial")
        raise OSError("boom")

    provider = _provider([_clip("AAA")], download=broken)
    with pytest.raises(ingest_service.IngestError):
        list(provider.fetch("", 1, "high"))
    assert not seen["dest"].exists()  # partial temp file cleaned up


def test_process_next_job_records_failure_category(tmp_path):
    root = tmp_path / "reels"
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    entry = appstate.register_library("Reels", root)
    appstate.enqueue_job(entry.id, "download", '{"count": 1}', source_permalink="", max_attempts=1)
    provider = _provider([_clip("AAA")], has_session=False)
    finished = ingest_service.process_next_job(appstate, root, provider)
    assert finished is not None
    assert finished.state == JOB_FAILED
    assert finished.public_error_code == "authentication_required"


def test_process_next_job_succeeds_and_catalogs(tmp_path):
    root = tmp_path / "reels"
    appstate = AppState.open(tmp_path / "appstate.sqlite3")
    entry = appstate.register_library("Reels", root)
    appstate.enqueue_job(entry.id, "download", '{"count": 2}', source_permalink="")
    provider = _provider([_clip("AAA"), _clip("BBB")])
    finished = ingest_service.process_next_job(appstate, root, provider)
    assert finished is not None and finished.state == JOB_SUCCEEDED
    assert query_library(root, ClipFilter()).matched == 2
