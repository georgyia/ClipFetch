"""Command-line entry point for ClipFetch."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from clipfetch import __version__
from clipfetch.errors import ClipFetchError
from clipfetch.ui import Console

MAX_WORKERS = 16


@dataclass(frozen=True)
class Options:
    """Validated command-line options."""

    reels: int
    out: Path
    workers: int
    headed: bool
    dry_run: bool


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
            "example: clipfetch -reels 25\n"
            "For personal use only — see the README for the full disclaimer."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-reels",
        metavar="COUNT",
        type=_positive_int,
        help="number of reels to download from your Instagram Reels feed",
    )
    parser.add_argument(
        "--out",
        metavar="DIR",
        type=Path,
        default=Path("reels"),
        help="output folder (default: ./reels)",
    )
    parser.add_argument(
        "--workers",
        metavar="N",
        type=_positive_int,
        default=8,
        help=f"parallel download workers, 1-{MAX_WORKERS} (default: 8)",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="show the browser window while collecting reels",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="collect and print video URLs without downloading",
    )
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def parse_args(argv: list[str] | None = None) -> Options:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.reels is None:
        parser.error("nothing to do — try: clipfetch -reels 25")
    if args.workers > MAX_WORKERS:
        parser.error(f"--workers must be at most {MAX_WORKERS}")
    return Options(
        reels=args.reels,
        out=args.out,
        workers=min(args.workers, args.reels),
        headed=args.headed,
        dry_run=args.dry_run,
    )


def main(argv: list[str] | None = None) -> int:
    try:
        opts = parse_args(argv)
    except SystemExit as exit_:  # argparse already printed help/error text
        return int(exit_.code or 0)

    console = Console()
    console.banner(__version__)
    console.dim("Personal use only — respect creators and Instagram's Terms of Use.")

    try:
        _run(opts, console)
    except KeyboardInterrupt:
        console.error("Interrupted.")
        return 130
    except ClipFetchError as err:
        console.error(str(err))
        return 1
    return 0


def _run(opts: Options, console: Console) -> None:
    """Collect reels from the feed and download them as they are found."""
    import time

    # Imported lazily so --help and unit tests never need the browser stack.
    from clipfetch import reels, session
    from clipfetch.downloader import DownloadPool
    from clipfetch.errors import DownloadError
    from clipfetch.ui import MultiProgress, Spinner, human_size

    if opts.dry_run:
        with session.instagram_session(console, headed=opts.headed) as context:
            with Spinner(console, f"Collecting reels… 0/{opts.reels}") as spinner:
                found = reels.collect_reels(
                    context,
                    opts.reels,
                    on_reel=lambda reel: None,
                    on_progress=lambda n: spinner.update(
                        f"Collecting reels… {n}/{opts.reels}"
                    ),
                )
        console.success(f"Collected {len(found)} of {opts.reels} reel(s).")
        for reel in found:
            console.print(f"  {reel.shortcode}  {reel.video_url}")
        return

    opts.out.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with session.instagram_session(console, headed=opts.headed) as context:
        with MultiProgress(console, opts.reels) as progress:
            pool = DownloadPool(opts.out, opts.workers, progress)
            found = reels.collect_reels(
                context,
                opts.reels,
                on_reel=pool.submit,
                on_progress=lambda n: progress.set_status(
                    f"Collecting reels… {n}/{opts.reels}"
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
            console.error(f"{result.reel.shortcode}: {result.error}")
    if not downloaded:
        raise DownloadError("No reels could be downloaded.")
    if len(found) < opts.reels:
        console.info(f"The feed only yielded {len(found)} reels this session.")
    console.success(
        f"Downloaded {len(downloaded)} reel(s) to {opts.out.resolve()} "
        f"({human_size(total_bytes)} in {elapsed:.0f}s)."
    )
