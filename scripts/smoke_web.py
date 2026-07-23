"""Clean-install smoke test for `clipfetch web` (issue #106).

Run after building the UI bundle and installing the package non-editably (``pip install ".[web]"``).
It proves the packaged bundle ships as package data and that the real ``clipfetch web`` console
script serves the single-page app and the API from one origin. It imports the *installed* package
(sys.path[0] is this script's directory, which has no ``clipfetch`` on it), so the source tree's
freshly built ``clipfetch/webui`` is not what gets checked — the wheel's copy is.

Usage: ``python scripts/smoke_web.py``  (exits non-zero on any failure).
"""

from __future__ import annotations

import subprocess
import sys
import time
import urllib.error
import urllib.request

PORT = 8137
BASE = f"http://127.0.0.1:{PORT}"
STARTUP_TIMEOUT = 30.0


def _get(path: str) -> tuple[int, str]:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=5) as resp:  # noqa: S310 - loopback only
        return resp.status, resp.read().decode("utf-8", "replace")


def _wait_ready() -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT
    while time.monotonic() < deadline:
        try:
            status, _ = _get("/health/live")
            if status == 200:
                return
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(0.25)
    raise SystemExit("server did not become ready in time")


def main() -> int:
    from clipfetch.api import static

    bundle = static.bundle_dir()
    if bundle is None:
        raise SystemExit("no UI bundle found — build it first: npm --prefix web run build")
    print(f"bundle: {bundle}")

    server = subprocess.Popen(
        ["clipfetch", "web", "--no-browser", "--host", "127.0.0.1", "--port", str(PORT)]
    )
    try:
        _wait_ready()

        status, body = _get("/")
        assert status == 200, f"/ returned {status}"
        assert 'id="root"' in body, "root element not served at /"

        status, body = _get("/explore/topic/cooking")
        assert status == 200 and 'id="root"' in body, "deep link did not fall back to the SPA"

        status, body = _get("/health/live")
        assert status == 200 and '"ok"' in body, "health probe failed"
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover
            server.kill()

    print("clipfetch web smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
