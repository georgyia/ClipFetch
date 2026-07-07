"""Error types raised by ClipFetch.

Every expected failure is a :class:`ClipFetchError` so the CLI can print a
friendly message instead of a traceback.
"""


class ClipFetchError(Exception):
    """Base class for all expected ClipFetch failures."""


class NotLoggedInError(ClipFetchError):
    """The browser profile has no valid Instagram session."""


class ExtractionError(ClipFetchError):
    """The feed did not yield the requested videos (layout/API change, stall)."""


class DownloadError(ClipFetchError):
    """A video could not be downloaded."""
