"""Account connection for in-app downloads: sign in to a platform once, from the UI.

Downloads reuse ClipFetch's own persistent browser profile (never your real browser or password).
The first time, a visible window opens so you sign in; the session is saved and later downloads run
headless. This service drives that one-time sign-in from Watch and reports connection status.

The sign-in itself and the display check are injected, so the state machine and the API are
testable offline with fakes; the real path (a headed Playwright window) is exercised behind the
``integration`` marker. Local single-user loopback only. Nothing here exposes cookies or paths.
"""

from __future__ import annotations

import os
import sys
import threading
from typing import Callable

from clipfetch.platforms.base import Platform

# Connection states (all safe to show the user).
STATE_UNKNOWN = "unknown"
STATE_CONNECTING = "connecting"
STATE_CONNECTED = "connected"
STATE_FAILED = "failed"
STATE_NO_DISPLAY = "no_display"

ConnectFn = Callable[[Platform], None]
DisplayCheck = Callable[[], bool]
Spawn = Callable[[Callable[[], None]], None]


class AccountError(RuntimeError):
    """An account request is invalid (e.g. an unknown or unsupported platform)."""


def _display_available() -> bool:
    """Whether a visible sign-in window can open here (a desktop, not a headless host)."""
    if sys.platform.startswith("linux"):
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    return True  # macOS and Windows always have a session display


def _default_spawn(run: Callable[[], None]) -> None:
    threading.Thread(target=run, name="clipfetch-signin", daemon=True).start()


def _real_connect(platform: Platform) -> None:
    """Open a headed sign-in window and block until signed in (or raise)."""
    from clipfetch import session
    from clipfetch.ui import Console

    with session.platform_session(platform, Console(), headed=True):
        pass  # entering the context completes (or fails) the one-time sign-in


def _support(platform: Platform) -> str:
    return "experimental" if platform.experimental else "full"


class AccountManager:
    """Tracks and drives per-platform sign-in; the sign-in runs off the request thread."""

    def __init__(
        self,
        platforms: list[Platform],
        *,
        connect_fn: ConnectFn = _real_connect,
        display_available: DisplayCheck = _display_available,
        spawn: Spawn = _default_spawn,
    ) -> None:
        self._platforms = {platform.key: platform for platform in platforms}
        self._connect_fn = connect_fn
        self._display_available = display_available
        self._spawn = spawn
        self._states: dict[str, str] = dict.fromkeys(self._platforms, STATE_UNKNOWN)
        self._lock = threading.Lock()

    def status(self) -> dict[str, object]:
        with self._lock:
            return {"accounts": [self._entry(key) for key in self._platforms]}

    def connect(self, key: str) -> dict[str, object]:
        platform = self._platforms.get(key)
        if platform is None:
            raise AccountError(f"unknown platform: {key}")
        if not self._display_available():
            self._set(key, STATE_NO_DISPLAY)
            return self._entry(key)
        self._set(key, STATE_CONNECTING)

        def run() -> None:
            try:
                self._connect_fn(platform)
            except Exception:  # noqa: BLE001 - any sign-in failure is surfaced as a safe state
                self._set(key, STATE_FAILED)
            else:
                self._set(key, STATE_CONNECTED)

        self._spawn(run)
        return self._entry(key)

    def _set(self, key: str, state: str) -> None:
        with self._lock:
            self._states[key] = state

    def _entry(self, key: str) -> dict[str, object]:
        platform = self._platforms[key]
        return {
            "platform": platform.key,
            "label": platform.label,
            "support": _support(platform),
            "state": self._states[key],
            "connected": self._states[key] == STATE_CONNECTED,
        }


def default_manager() -> AccountManager:
    """An AccountManager over the connectable platforms (session-based sign-in)."""
    from clipfetch.platforms import ALL

    return AccountManager(list(ALL))
