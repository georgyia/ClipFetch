"""Browser session management for any platform.

ClipFetch never touches your real browser or your password. It keeps its own
Chromium profile under ``~/.clipfetch``: the first run opens a visible window
where you sign in once, and the session cookie persists there for every later
(headless) run. Each platform gets its own profile so logins never collide.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import BrowserContext, Playwright, sync_playwright

from clipfetch.constants import USER_AGENT
from clipfetch.errors import NotLoggedInError
from clipfetch.platforms.base import Platform
from clipfetch.ui import Console, Spinner

CLIPFETCH_HOME = Path.home() / ".clipfetch"
LOGIN_TIMEOUT_S = 300
_POLL_INTERVAL_S = 2


def profile_dir(platform: Platform) -> Path:
    """Where a platform's persistent browser profile lives.

    Instagram keeps the original ``~/.clipfetch/profile`` path so sessions
    created before multi-platform support are not invalidated.
    """
    if platform.key == "instagram":
        return CLIPFETCH_HOME / "profile"
    return CLIPFETCH_HOME / f"profile-{platform.key}"


def _launch(playwright: Playwright, profile: Path, headless: bool) -> BrowserContext:
    profile.mkdir(parents=True, exist_ok=True)
    return playwright.chromium.launch_persistent_context(
        profile,
        headless=headless,
        viewport={"width": 1280, "height": 900},
        user_agent=USER_AGENT if headless else None,
    )


def cookie_header(context: BrowserContext, platform: Platform) -> str:
    """A ``Cookie:`` header string for the platform's site.

    Some CDNs (TikTok) reject the browser-free downloader without the session's
    cookies; capturing them lets urllib present the same identity.
    """
    url = f"https://www.{platform.host}/"
    pairs = [f"{c['name']}={c['value']}" for c in context.cookies(url) if c.get("value")]
    return "; ".join(pairs)


def has_session_cookie(context: BrowserContext, platform: Platform) -> bool:
    """Whether the profile holds a valid session cookie for the platform."""
    if platform.session_cookie is None:
        return True  # login not enforced for this platform
    now = time.time()
    for cookie in context.cookies(f"https://www.{platform.host}/"):
        if cookie["name"] == platform.session_cookie and cookie["value"]:
            if cookie.get("expires", -1) in (-1, None) or cookie["expires"] > now:
                return True
    return False


def _wait_for_login(
    context: BrowserContext, platform: Platform, console: Console, timeout_s: float
) -> None:
    """Block until the user signs in inside the opened window."""
    deadline = time.monotonic() + timeout_s
    with Spinner(console, f"Waiting for you to sign in to {platform.label}…"):
        while time.monotonic() < deadline:
            if not context.pages:  # user closed the window
                raise NotLoggedInError("The browser window was closed before signing in.")
            if has_session_cookie(context, platform):
                return
            time.sleep(_POLL_INTERVAL_S)
    wait = f"{timeout_s / 60:.0f} minutes" if timeout_s >= 120 else f"{timeout_s:.0f} seconds"
    raise NotLoggedInError(f"No sign-in detected within {wait} — please try again.")


@contextmanager
def platform_session(
    platform: Platform,
    console: Console,
    headed: bool = False,
    login_timeout_s: float = LOGIN_TIMEOUT_S,
    prepare: Callable[[BrowserContext], None] | None = None,
) -> Iterator[BrowserContext]:
    """Yield a browser context signed in to ``platform``.

    ``prepare`` is an optional hook run against the fresh context before the
    login check (used to inject imported cookies). If the profile has no
    session yet and the platform enforces login, a visible window is opened
    for a one-time sign-in.
    """
    profile = profile_dir(platform)
    with sync_playwright() as playwright:
        context = _launch(playwright, profile, headless=not headed)
        try:
            if prepare is not None:
                prepare(context)
            if not has_session_cookie(context, platform):
                console.warning_box(
                    f"{platform.label} sign-in required",
                    [
                        "ClipFetch uses its own browser profile, so you need to",
                        f"sign in to {platform.label} once. A browser window is",
                        "opening — your session (not your password) is saved.",
                    ],
                )
                if not headed:  # the login window must be visible
                    context.close()
                    context = _launch(playwright, profile, headless=False)
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(platform.login_url)
                _wait_for_login(context, platform, console, login_timeout_s)
                console.success("Signed in — session saved for future runs.")
            yield context
        finally:
            context.close()
