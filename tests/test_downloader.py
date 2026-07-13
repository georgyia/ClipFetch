import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from clipfetch.downloader import (
    DownloadPool,
    existing_idents,
    filename_for,
    write_sidecar,
)
from clipfetch.model import Clip
from clipfetch.ui import Console, MultiProgress


class _VideoHandler(BaseHTTPRequestHandler):
    """Serves /video/<name> as deterministic bytes; everything else 404s."""

    def do_GET(self):
        if not self.path.startswith(("/video/", "/ignore-range/")):
            self.send_error(404)
            return
        body = self.path.rsplit("/", 1)[-1].encode() * 5000
        range_header = self.headers.get("Range")
        if range_header and self.path.startswith("/video/"):
            start = int(range_header.removeprefix("bytes=").removesuffix("-"))
            if start >= len(body):
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{len(body)}")
                self.end_headers()
                return
            partial = body[start:]
            self.send_response(206)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(partial)))
            self.send_header("Content-Range", f"bytes {start}-{len(body) - 1}/{len(body)}")
            self.end_headers()
            self.wfile.write(partial)
            return
        self.send_response(200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # keep test output clean


@pytest.fixture
def video_server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _VideoHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def _clip(ident, url):
    return Clip("instagram", ident, url)


def _pool(tmp_path, progress, workers=4):
    return DownloadPool(tmp_path, "reel", workers, progress)


def _progress():
    return MultiProgress(Console(io.StringIO()), overall_total=3)


def test_filename_is_deterministic_and_sanitised():
    assert filename_for("reel", 1, _clip("ABC", "u")) == "reel_001_ABC.mp4"
    assert filename_for("tiktok", 42, _clip("a/b?c", "u")) == "tiktok_042_abc.mp4"


def test_existing_idents_scans_completed_downloads(tmp_path):
    (tmp_path / "reel_001_ABC.mp4").write_bytes(b"x")
    (tmp_path / "reel_002_DEF.mp4").write_bytes(b"y")
    (tmp_path / "reel_003_EMPTY.mp4").write_bytes(b"")  # zero-byte: not complete
    (tmp_path / "tiktok_001_OTHER.mp4").write_bytes(b"z")  # different noun
    assert existing_idents(tmp_path, "reel") == {"ABC", "DEF"}


def test_parallel_downloads_write_complete_files(tmp_path, video_server):
    clips = [_clip(f"CODE{i}", f"{video_server}/video/clip{i}") for i in range(3)]
    progress = _progress()
    pool = _pool(tmp_path, progress)
    with progress:
        for clip in clips:
            pool.submit(clip)
        results = pool.wait()

    assert all(r.ok for r in results)
    assert [r.clip for r in results] == clips  # results keep submit order
    for i, result in enumerate(results):
        assert result.path == tmp_path / f"reel_{i + 1:03d}_CODE{i}.mp4"
        assert result.path.read_bytes() == f"clip{i}".encode() * 5000
        assert result.size == result.path.stat().st_size
    assert not list(tmp_path.glob("*.part"))  # no leftover temp files


def test_existing_file_is_skipped_not_refetched(tmp_path, video_server):
    (tmp_path / "reel_001_DONE.mp4").write_bytes(b"already here")
    progress = _progress()
    pool = _pool(tmp_path, progress)
    with progress:
        pool.submit(_clip("DONE", f"{video_server}/video/should_not_be_used"))
        (result,) = pool.wait()
    assert result.ok and result.skipped
    assert (tmp_path / "reel_001_DONE.mp4").read_bytes() == b"already here"


def test_write_sidecar_contains_clip_metadata(tmp_path):
    video = tmp_path / "reel_001_ABC.mp4"
    clip = Clip(
        "instagram", "ABC", "https://cdn.test/abc.mp4",
        url="https://www.instagram.com/reel/ABC/",
        author="nasa", caption="space", likes=42,
    )
    sidecar = write_sidecar(video, clip)
    assert sidecar == tmp_path / "reel_001_ABC.json"
    assert json.loads(sidecar.read_text(encoding="utf-8")) == {
        "platform": "instagram",
        "id": "ABC",
        "url": "https://www.instagram.com/reel/ABC/",
        "author": "nasa",
        "caption": "space",
        "likes": 42,
    }


def test_pool_writes_sidecars_only_when_enabled(tmp_path, video_server):
    clip = _clip("CODE0", f"{video_server}/video/clip0")

    progress = _progress()
    with progress:
        pool = DownloadPool(tmp_path, "reel", 2, progress, metadata=True)
        pool.submit(clip)
        (result,) = pool.wait()
    assert result.ok
    sidecar = tmp_path / "reel_001_CODE0.json"
    assert json.loads(sidecar.read_text(encoding="utf-8"))["id"] == "CODE0"

    other = tmp_path / "no_meta"
    other.mkdir()
    progress = _progress()
    with progress:
        pool = DownloadPool(other, "reel", 2, progress)  # metadata off (default)
        pool.submit(clip)
        (result,) = pool.wait()
    assert result.ok
    assert not list(other.glob("*.json"))


def test_pool_backfills_sidecar_for_skipped_existing_file(tmp_path, video_server):
    (tmp_path / "reel_001_DONE.mp4").write_bytes(b"already here")
    progress = _progress()
    with progress:
        pool = DownloadPool(tmp_path, "reel", 2, progress, metadata=True)
        pool.submit(_clip("DONE", f"{video_server}/video/unused"))
        (result,) = pool.wait()
    assert result.skipped
    assert (tmp_path / "reel_001_DONE.json").exists()


def test_failed_download_reports_error_and_cleans_up(tmp_path, video_server):
    progress = _progress()
    pool = _pool(tmp_path, progress)
    with progress:
        pool.submit(_clip("GOOD", f"{video_server}/video/ok"))
        pool.submit(_clip("BAD", f"{video_server}/missing"))
        results = pool.wait()

    good, bad = results
    assert good.ok
    assert not bad.ok and "404" in bad.error
    assert bad.path is None
    assert not list(tmp_path.glob("*.part"))


def test_partial_download_resumes_with_range_even_if_index_changed(tmp_path, video_server):
    body = b"resumable" * 5000
    partial = tmp_path / "reel_009_CODE.part"
    partial.write_bytes(body[:12345])
    progress = _progress()
    with progress:
        pool = _pool(tmp_path, progress)
        pool.submit(_clip("CODE", f"{video_server}/video/resumable"))
        (result,) = pool.wait()

    assert result.ok
    assert result.path == tmp_path / "reel_009_CODE.mp4"
    assert result.path.read_bytes() == body
    assert result.size == len(body)


def test_range_ignored_restarts_instead_of_appending(tmp_path, video_server):
    partial = tmp_path / "reel_001_CODE.part"
    partial.write_bytes(b"stale-prefix")
    progress = _progress()
    with progress:
        pool = _pool(tmp_path, progress)
        pool.submit(_clip("CODE", f"{video_server}/ignore-range/fresh"))
        (result,) = pool.wait()

    assert result.ok
    assert result.path.read_bytes() == b"fresh" * 5000


def test_failed_resume_preserves_partial_for_fresh_url_next_run(tmp_path, video_server):
    partial = tmp_path / "reel_001_CODE.part"
    partial.write_bytes(b"keep me")
    progress = _progress()
    with progress:
        pool = _pool(tmp_path, progress)
        pool.submit(_clip("CODE", f"{video_server}/missing"))
        (result,) = pool.wait()

    assert not result.ok
    assert partial.read_bytes() == b"keep me"
