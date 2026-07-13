"""Real-browser collect/download smoke test against a local fixture server."""

from __future__ import annotations

import io
import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from playwright.sync_api import sync_playwright

from clipfetch.collector import collect
from clipfetch.downloader import DownloadPool
from clipfetch.model import Clip, Quality
from clipfetch.platforms.base import Platform
from clipfetch.ui import Console, MultiProgress

pytestmark = pytest.mark.integration
_VIDEO = b"clipfetch-browser-integration-fixture" * 2048


class _FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/feed":
            body = b"""<!doctype html><body>fixture<script>
fetch('/api/feed').then(response => response.json())
  .then(() => document.body.dataset.loaded = 'true');
</script></body>"""
            self._send(200, "text/html", body)
        elif self.path == "/api/feed":
            port = self.server.server_port
            body = json.dumps({
                "items": [{
                    "id": "LOCAL1",
                    "video_url": f"http://127.0.0.1:{port}/video/LOCAL1",
                }]
            }).encode()
            self._send(200, "application/json", body)
        elif self.path == "/video/LOCAL1":
            self._send(200, "video/mp4", _VIDEO)
        else:
            self.send_error(404)

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


class _FixturePlatform(Platform):
    key = "fixture"
    label = "Fixture"
    flag = "fixtures"
    noun = "fixture"
    host = "127.0.0.1"
    login_url = ""

    def __init__(self, origin: str) -> None:
        self.origin = origin

    def feed_url(self, target: str | None = None) -> str:
        return f"{self.origin}/feed"

    def find_clips(self, payload, quality: Quality) -> Iterator[Clip]:
        for item in payload.get("items", []):
            if item.get("id") and item.get("video_url"):
                yield Clip(self.key, item["id"], item["video_url"])


@pytest.fixture
def fixture_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()


def test_real_chromium_collects_and_downloads_local_fixture(tmp_path, fixture_server):
    platform = _FixturePlatform(fixture_server)
    progress = MultiProgress(Console(io.StringIO()), 1, noun=platform.noun)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        try:
            with progress:
                pool = DownloadPool(tmp_path, platform.noun, 1, progress)
                clips = collect(
                    context,
                    platform,
                    Quality.HIGH,
                    1,
                    on_clip=pool.submit,
                    stall_timeout_s=5,
                )
                results = pool.wait()
        finally:
            context.close()
            browser.close()

    assert [clip.ident for clip in clips] == ["LOCAL1"]
    assert len(results) == 1 and results[0].ok
    assert results[0].path.read_bytes() == _VIDEO
