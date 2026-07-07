import io
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from clipfetch.downloader import DownloadPool
from clipfetch.reels import Reel
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


def _pool(tmp_path, workers=4):
    progress = MultiProgress(Console(io.StringIO()), overall_total=3)
    return DownloadPool(tmp_path, workers, progress), progress


def test_parallel_downloads_write_complete_files(tmp_path, video_server):
    reels = [Reel(f"CODE{i}", f"{video_server}/video/clip{i}") for i in range(3)]
    pool, progress = _pool(tmp_path)
    with progress:
        for reel in reels:
            pool.submit(reel)
        results = pool.wait()

    assert all(r.ok for r in results)
    assert [r.reel for r in results] == reels  # results keep submit order
    for i, result in enumerate(results):
        assert result.path == tmp_path / f"reel_{i + 1:03d}_CODE{i}.mp4"
        assert result.path.read_bytes() == f"clip{i}".encode() * 5000
        assert result.size == result.path.stat().st_size
    assert not list(tmp_path.glob("*.part"))  # no leftover temp files


def test_failed_download_reports_error_and_cleans_up(tmp_path, video_server):
    pool, progress = _pool(tmp_path)
    with progress:
        pool.submit(Reel("GOOD", f"{video_server}/video/ok"))
        pool.submit(Reel("BAD", f"{video_server}/missing"))
        results = pool.wait()

    good, bad = results
    assert good.ok
    assert not bad.ok and "404" in bad.error
    assert bad.path is None
    assert not list(tmp_path.glob("*.part"))
