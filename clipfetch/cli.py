"""Command-line entry point for ClipFetch."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from clipfetch import __version__, platforms
from clipfetch.errors import ClipFetchError
from clipfetch.model import Quality
from clipfetch.platforms.base import Platform
from clipfetch.ui import Console

MAX_WORKERS = 16


@dataclass(frozen=True)
class Options:
    """Validated command-line options for a download run."""

    platform: Platform
    count: int
    target: Optional[str]
    out: Path
    workers: int
    quality: Quality
    headed: bool
    dry_run: bool
    import_cookies: Optional[str]


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a number")
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clipfetch",
        description="Download short-form videos from your feed to watch offline.",
        epilog=(
            "examples:\n"
            "  clipfetch -reels 25            download 25 reels from your feed\n"
            "  clipfetch -reels 10 @nasa      download an account's reels\n"
            "  clipfetch watch reels          play a downloaded folder\n"
            "For personal use only — see the README for the full disclaimer."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    source = parser.add_argument_group("sources (choose one)")
    for platform in platforms.ALL:
        note = " (experimental)" if platform.experimental else ""
        source.add_argument(
            f"-{platform.flag}",
            metavar="COUNT",
            type=_positive_int,
            help=f"number of {platform.noun}s to download from {platform.label}{note}",
        )
    parser.add_argument(
        "target",
        nargs="?",
        metavar="@ACCOUNT",
        help="limit to one account's clips (supported sources only)",
    )
    parser.add_argument(
        "--out",
        metavar="DIR",
        type=Path,
        help="output folder (default: named after the source, e.g. ./reels)",
    )
    parser.add_argument(
        "--workers",
        metavar="N",
        type=_positive_int,
        default=8,
        help=f"parallel download workers, 1-{MAX_WORKERS} (default: 8)",
    )
    parser.add_argument(
        "--quality",
        choices=[q.value for q in Quality],
        default=Quality.HIGH.value,
        help="preferred rendition when several exist (default: high)",
    )
    parser.add_argument(
        "--import-cookies",
        metavar="BROWSER",
        choices=["chrome"],
        help="reuse an existing login from your real browser (macOS Chrome)",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="show the browser window while collecting",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="collect and print video URLs without downloading",
    )
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def parse_args(argv: Optional[list[str]] = None) -> Options:
    parser = build_parser()
    args = parser.parse_args(argv)

    chosen = [p for p in platforms.ALL if getattr(args, p.flag) is not None]
    if not chosen:
        flags = " | ".join(f"-{p.flag} N" for p in platforms.ALL)
        parser.error(f"nothing to do — try one of: {flags}")
    if len(chosen) > 1:
        parser.error("choose a single source at a time")
    platform = chosen[0]
    count = getattr(args, platform.flag)

    if args.workers > MAX_WORKERS:
        parser.error(f"--workers must be at most {MAX_WORKERS}")

    target = args.target.lstrip("@") if args.target else None
    if target and not platform.supports_target:
        parser.error(f"{platform.label} does not support downloading a single account")

    return Options(
        platform=platform,
        count=count,
        target=target,
        out=args.out or Path(platform.flag),
        workers=min(args.workers, count),
        quality=Quality(args.quality),
        headed=args.headed,
        dry_run=args.dry_run,
        import_cookies=args.import_cookies,
    )


def _run_watch(args: list[str], console: Console) -> int:
    from clipfetch.watcher import watch

    parser = argparse.ArgumentParser(prog="clipfetch watch")
    parser.add_argument("dir", nargs="?", default="reels", type=Path,
                        help="folder of downloaded clips (default: ./reels)")
    parser.add_argument("--shuffle", action="store_true", help="play in random order")
    try:
        parsed = parser.parse_args(args)
    except SystemExit as exit_:
        return int(exit_.code or 0)
    return watch(parsed.dir, console, shuffle=parsed.shuffle)


def main(argv: Optional[list[str]] = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    console = Console()

    if args and args[0] == "watch":
        console.banner(__version__)
        console.dim("Personal use only — respect creators and platform Terms of Use.")
        return _run_watch(args[1:], console)

    try:
        opts = parse_args(args)
    except SystemExit as exit_:  # argparse already printed help/error text
        return int(exit_.code or 0)

    console.banner(__version__)
    console.dim("Personal use only — respect creators and platform Terms of Use.")

    try:
        _run(opts, console)
    except KeyboardInterrupt:
        console.error("Interrupted.")
        return 130
    except ClipFetchError as err:
        console.error(str(err))
        return 1
    return 0


def _cookie_importer(opts: Options, platform: Platform, console: Console):
    """Build a session-prepare hook that injects imported browser cookies."""
    if not opts.import_cookies:
        return None

    def prepare(context) -> None:
        from clipfetch.cookies import CookieImportError, import_session_cookies

        try:
            cookies = import_session_cookies(platform, opts.import_cookies)
            context.add_cookies(cookies)
            console.success(
                f"Imported {len(cookies)} {platform.label} cookie(s) from "
                f"{opts.import_cookies}."
            )
        except CookieImportError as err:
            console.error(f"Cookie import failed: {err}")
            console.info("Falling back to ClipFetch's own sign-in.")

    return prepare


def _run(opts: Options, console: Console) -> None:
    """Collect clips from the feed and download them as they are found."""
    import time

    # Imported lazily so --help and unit tests never need the browser stack.
    from clipfetch import collector, session
    from clipfetch.downloader import DownloadPool, clean_partials, existing_idents
    from clipfetch.errors import DownloadError
    from clipfetch.ui import MultiProgress, Spinner, human_size

    platform = opts.platform
    noun = platform.noun
    source = f"@{opts.target}" if opts.target else f"your {platform.label} feed"
    console.info(f"Source: {source}")

    prepare = _cookie_importer(opts, platform, console)
    if platform.experimental and not opts.dry_run:
        console.info(
            f"{platform.label} support is experimental — extraction is reliable, "
            "but downloads are often blocked by anti-bot. Try --dry-run to list URLs."
        )

    if opts.dry_run:
        with session.platform_session(platform, console, headed=opts.headed, prepare=prepare) as context:
            with Spinner(console, f"Collecting {noun}s… 0/{opts.count}") as spinner:
                found = collector.collect(
                    context, platform, opts.quality, opts.count,
                    on_clip=lambda clip: None,
                    target=opts.target,
                    on_progress=lambda n: spinner.update(
                        f"Collecting {noun}s… {n}/{opts.count}"
                    ),
                )
        console.success(f"Collected {len(found)} of {opts.count} {noun}(s).")
        for clip in found:
            console.print(f"  {clip.ident}  {clip.video_url}")
        return

    opts.out.mkdir(parents=True, exist_ok=True)
    clean_partials(opts.out)
    already_have = existing_idents(opts.out, noun)
    if already_have:
        console.info(f"Skipping {len(already_have)} {noun}(s) already in {opts.out}.")

    started = time.monotonic()
    with session.platform_session(platform, console, headed=opts.headed, prepare=prepare) as context:
        if platform.needs_browser_download:
            from clipfetch import browser_download

            with Spinner(console, f"Collecting {noun}s… 0/{opts.count}") as spinner:
                found = collector.collect(
                    context, platform, opts.quality, opts.count,
                    on_clip=lambda clip: None,
                    target=opts.target,
                    already_have=already_have,
                    on_progress=lambda n: spinner.update(
                        f"Collecting {noun}s… {n}/{opts.count}"
                    ),
                )
            console.info(f"Downloading {len(found)} {noun}(s) through the browser…")
            results = browser_download.download_all(context, found, opts.out, noun, console)
        else:
            headers = {"Cookie": session.cookie_header(context, platform)}
            with MultiProgress(console, opts.count) as progress:
                pool = DownloadPool(
                    opts.out, noun, opts.workers, progress, extra_headers=headers
                )
                found = collector.collect(
                    context, platform, opts.quality, opts.count,
                    on_clip=pool.submit,
                    target=opts.target,
                    already_have=already_have,
                    on_progress=lambda n: progress.set_status(
                        f"Collecting {noun}s… {n}/{opts.count}"
                    ),
                )
                progress.set_status("Feed done — finishing downloads…")
                results = pool.wait()
                progress.set_status("")
    elapsed = time.monotonic() - started

    downloaded = [r for r in results if r.ok]
    total_bytes = sum(r.size for r in downloaded)
    for result in results:
        if not result.ok:
            console.error(f"{result.clip.ident}: {result.error}")
    if not downloaded:
        if platform.experimental:
            raise DownloadError(
                f"No {noun}s could be downloaded — {platform.label} blocked the "
                "requests (anti-bot). Extraction still works: try --dry-run to get "
                "the video URLs."
            )
        raise DownloadError(f"No {noun}s could be downloaded.")
    if len(found) < opts.count:
        console.info(f"The feed only yielded {len(found)} {noun}s this session.")
    console.success(
        f"Downloaded {len(downloaded)} {noun}(s) to {opts.out.resolve()} "
        f"({human_size(total_bytes)} in {elapsed:.0f}s)."
    )
