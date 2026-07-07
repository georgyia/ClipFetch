import io
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from clipfetch.downloader import DownloadPool, filename_for
from clipfetch.model import Clip
from clipfetch.ui import Console, MultiProgress


class _VideoHandler(BaseHTTPRequestHandler):
    """Serves /video/<name> as deterministic bytes; everything else 404s."""

    def do_GET(self):
        if not self.path.startswith("/video/"):
            self.send_error(404)
            return
        body = self.path.rsplit("/", 1)[-1].encode() * 5000
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
