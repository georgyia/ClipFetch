"""Instagram browser session management.

ClipFetch never touches your real browser or your password. It keeps its own
Chromium profile under ``~/.clipfetch/profile``: the first run opens a visible
window where you sign in to Instagram once, and the session cookie persists
there for every later (headless) run.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from playwright.sync_api import BrowserContext, Playwright, sync_playwright

from clipfetch.errors import NotLoggedInError
from clipfetch.ui import Console, Spinner

PROFILE_DIR = Path.home() / ".clipfetch" / "profile"
INSTAGRAM_URL = "https://www.instagram.com/"
LOGIN_URL = INSTAGRAM_URL + "accounts/login/"
LOGIN_TIMEOUT_S = 300
_POLL_INTERVAL_S = 2

# Instagram serves a login wall to browsers that advertise themselves as
# headless, so headless runs claim the equivalent regular Chrome UA.
_HEADLESS_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def _launch(playwright: Playwright, headless: bool) -> BrowserContext:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    return playwright.chromium.launch_persistent_context(
        PROFILE_DIR,
        headless=headless,
        viewport={"width": 1280, "height": 900},
        user_agent=_HEADLESS_USER_AGENT if headless else None,
    )


def has_session_cookie(context: BrowserContext) -> bool:
    """Whether the profile holds an Instagram session cookie."""
    now = time.time()
    for cookie in context.cookies(INSTAGRAM_URL):
        if cookie["name"] == "sessionid" and cookie["value"]:
            if cookie.get("expires", -1) in (-1, None) or cookie["expires"] > now:
                return True
    return False


def _wait_for_login(context: BrowserContext, console: Console, timeout_s: float) -> None:
    """Block until the user signs in inside the opened window."""
    deadline = time.monotonic() + timeout_s
    with Spinner(console, "Waiting for you to sign in to Instagram…"):
        while time.monotonic() < deadline:
            if not context.pages:  # user closed the window
                raise NotLoggedInError("The browser window was closed before signing in.")
            if has_session_cookie(context):
                return
            time.sleep(_POLL_INTERVAL_S)
    wait = f"{timeout_s / 60:.0f} minutes" if timeout_s >= 120 else f"{timeout_s:.0f} seconds"
    raise NotLoggedInError(f"No sign-in detected within {wait} — please try again.")


@contextmanager
def instagram_session(
    console: Console,
    headed: bool = False,
    login_timeout_s: float = LOGIN_TIMEOUT_S,
) -> Iterator[BrowserContext]:
    """Yield a browser context that is signed in to Instagram.

    If the profile has no session yet, a visible window is opened for a
    one-time sign-in and the flow continues once the session cookie appears.
    """
    with sync_playwright() as playwright:
        context = _launch(playwright, headless=not headed)
        try:
            if not has_session_cookie(context):
                console.warning_box(
                    "Instagram sign-in required",
                    [
                        "ClipFetch uses its own browser profile, so you need to",
                        "sign in to Instagram once. A browser window is opening —",
                        "your session (not your password) is saved for next time.",
                    ],
                )
                if not headed:  # the login window must be visible
                    context.close()
                    context = _launch(playwright, headless=False)
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(LOGIN_URL)
                _wait_for_login(context, console, login_timeout_s)
                console.success("Signed in — session saved for future runs.")
            yield context
        finally:
            context.close()
