"""Command-line entry point for ClipFetch."""

from __future__ import annotations

import sys

from clipfetch import __version__

USAGE = f"""\
ClipFetch v{__version__} — download short-form videos from your feed.

Usage:
  clipfetch -reels <count> [options]

Options:
  -reels <count>     Number of reels to download from your Instagram Reels feed.
  --help, -h         Show this help message.
  --version          Show the version.
"""


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args or "-h" in args or "--help" in args:
        print(USAGE)
        return 0
    if "--version" in args:
        print(__version__)
        return 0
    print(USAGE)
    return 2
