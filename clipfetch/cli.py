"""Command-line entry point for ClipFetch."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

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
    target: str | None
    out: Path
    workers: int
    quality: Quality
    headed: bool
    dry_run: bool
    import_cookies: str | None
    metadata: bool


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a number") from None
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def _nonnegative_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a number") from None
    if number < 0:
        raise argparse.ArgumentTypeError("must be at least 0")
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
        choices=["chrome", "firefox", "safari"],
        help="reuse an existing login from Chrome, Firefox, or Safari",
    )
    parser.add_argument(
        "--metadata",
        action="store_true",
        help="save normalized platform metadata as schema-v2 JSON next to each clip",
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


def parse_args(argv: list[str] | None = None) -> Options:
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
        metadata=args.metadata,
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


def _run_library(args: list[str], console: Console) -> int:
    """Dispatch catalog maintenance commands without importing browser code."""
    from clipfetch.catalog import CatalogError, index_library
    from clipfetch.library import (
        ClipFilter,
        find_clip,
        parse_date,
        parse_magnitude,
        query_library,
        query_to_dict,
        record_to_dict,
    )
    from clipfetch.semantic import SemanticError

    def magnitude(value: str) -> int:
        try:
            return parse_magnitude(value)
        except ValueError as err:
            raise argparse.ArgumentTypeError(str(err)) from err

    def date_value(value: str):
        try:
            return parse_date(value)
        except ValueError as err:
            raise argparse.ArgumentTypeError(str(err)) from err

    parser = argparse.ArgumentParser(prog="clipfetch library")
    commands = parser.add_subparsers(dest="command", required=True)
    index_parser = commands.add_parser(
        "index", help="index existing videos and reconcile the local catalog"
    )
    index_parser.add_argument("dir", nargs="?", default="reels", type=Path)
    list_parser = commands.add_parser("list", help="list and filter cataloged clips")
    list_parser.add_argument("dir", nargs="?", default="reels", type=Path)
    list_parser.add_argument("--min-likes", type=magnitude)
    list_parser.add_argument("--max-likes", type=magnitude)
    list_parser.add_argument("--min-views", type=magnitude)
    list_parser.add_argument("--max-views", type=magnitude)
    list_parser.add_argument("--author", action="append", default=[])
    list_parser.add_argument("--hashtag", action="append", default=[])
    list_parser.add_argument("--platform", action="append", default=[])
    list_parser.add_argument("--downloaded-after", type=date_value)
    list_parser.add_argument("--downloaded-before", type=date_value)
    list_parser.add_argument(
        "--sort", choices=["likes", "views", "date", "author"], default="date"
    )
    list_parser.add_argument("--limit", type=_positive_int)
    list_parser.add_argument("--offset", type=_nonnegative_int, default=0)
    list_parser.add_argument("--json", action="store_true")
    info_parser = commands.add_parser("info", help="show all metadata for one clip id")
    info_parser.add_argument("values", nargs="+", metavar="[DIR] CLIP_ID")
    info_parser.add_argument("--json", action="store_true")
    semantic_parser = commands.add_parser(
        "semantic-index", help="build/update the optional local semantic index"
    )
    semantic_parser.add_argument("dir", nargs="?", default="reels", type=Path)
    semantic_parser.add_argument("--batch-size", type=_positive_int, default=32)
    search_parser = commands.add_parser("search", help="search captions and hashtags by meaning")
    search_parser.add_argument("values", nargs="+", metavar="[DIR] QUERY")
    search_parser.add_argument("--min-likes", type=magnitude)
    search_parser.add_argument("--max-likes", type=magnitude)
    search_parser.add_argument("--min-views", type=magnitude)
    search_parser.add_argument("--max-views", type=magnitude)
    search_parser.add_argument("--author", action="append", default=[])
    search_parser.add_argument("--hashtag", action="append", default=[])
    search_parser.add_argument("--platform", action="append", default=[])
    search_parser.add_argument("--downloaded-after", type=date_value)
    search_parser.add_argument("--downloaded-before", type=date_value)
    search_parser.add_argument("--limit", type=_positive_int, default=20)
    search_parser.add_argument("--json", action="store_true")
    try:
        parsed = parser.parse_args(args)
    except SystemExit as exit_:
        return int(exit_.code or 0)
    try:
        if parsed.command == "index":
            catalog_report = index_library(parsed.dir)
            console.success(
                "Catalog indexed: "
                f"{catalog_report.scanned} scanned, {catalog_report.inserted} inserted, "
                f"{catalog_report.updated} updated, {catalog_report.unchanged} unchanged, "
                f"{catalog_report.missing} missing, "
                f"{catalog_report.malformed_sidecars} malformed sidecar(s)."
            )
            return 0
        if parsed.command == "list":
            filters = ClipFilter(
                min_likes=parsed.min_likes,
                max_likes=parsed.max_likes,
                min_views=parsed.min_views,
                max_views=parsed.max_views,
                authors=tuple(parsed.author),
                hashtags=tuple(parsed.hashtag),
                platforms=tuple(parsed.platform),
                downloaded_after=parsed.downloaded_after,
                downloaded_before=parsed.downloaded_before,
            )
            list_result = query_library(
                parsed.dir,
                filters,
                sort=parsed.sort,
                limit=parsed.limit,
                offset=parsed.offset,
            )
            if parsed.json:
                console.print(
                    json.dumps(query_to_dict(list_result), ensure_ascii=False, indent=2)
                )
            else:
                _print_library_table(list_result.clips, console)
                console.info(
                    f"{list_result.matched} matched, {list_result.excluded} excluded, "
                    f"{list_result.unknown_required_metadata} lacked required metadata."
                )
            return 0
        if parsed.command == "semantic-index":
            from clipfetch.semantic import DEFAULT_CACHE_DIR, FastEmbedder, semantic_index

            if not DEFAULT_CACHE_DIR.exists():
                console.info(
                    f"First use downloads about 220 MB to {DEFAULT_CACHE_DIR}; "
                    "captions and vectors stay local."
                )
            embedder = FastEmbedder()
            last_progress = 0

            def show_progress(done: int, total: int) -> None:
                nonlocal last_progress
                if done == total or done - last_progress >= parsed.batch_size:
                    console.info(f"Semantic indexing: {done}/{total}")
                    last_progress = done

            semantic_report = semantic_index(
                parsed.dir,
                embedder,
                batch_size=parsed.batch_size,
                on_progress=show_progress,
            )
            console.success(
                f"Semantic index: {semantic_report.scanned} scanned, "
                f"{semantic_report.indexed} indexed, "
                f"{semantic_report.unchanged} unchanged, {semantic_report.empty} empty."
            )
            return 0
        if parsed.command == "search":
            from clipfetch.semantic import FastEmbedder, semantic_search

            if len(parsed.values) == 1:
                root, query = Path("reels"), parsed.values[0]
            else:
                root, query = Path(parsed.values[0]), " ".join(parsed.values[1:])
            filters = ClipFilter(
                min_likes=parsed.min_likes,
                max_likes=parsed.max_likes,
                min_views=parsed.min_views,
                max_views=parsed.max_views,
                authors=tuple(parsed.author),
                hashtags=tuple(parsed.hashtag),
                platforms=tuple(parsed.platform),
                downloaded_after=parsed.downloaded_after,
                downloaded_before=parsed.downloaded_before,
            )
            embedder = FastEmbedder()
            search_result = semantic_search(
                root, query, embedder, filters=filters, limit=parsed.limit
            )
            if parsed.json:
                value = {
                    "schema_version": 1,
                    "model_id": embedder.model_id,
                    "model_revision": embedder.revision,
                    "query": query,
                    "considered": search_result.considered,
                    "unindexed": search_result.unindexed,
                    "matches": [
                        {"score": match.score, "clip": record_to_dict(match.record)}
                        for match in search_result.matches
                    ],
                }
                console.print(json.dumps(value, ensure_ascii=False, indent=2))
            else:
                for match in search_result.matches:
                    console.print(
                        f"{match.score:.3f}  {match.record.clip_id}  "
                        f"{match.record.author or '?'}  {match.record.relative_path}"
                    )
                console.info(
                    f"{len(search_result.matches)} result(s); "
                    f"{search_result.unindexed} matching clip(s) "
                    "were not indexed."
                )
            return 0
        if len(parsed.values) == 1:
            root, clip_id = Path("reels"), parsed.values[0]
        elif len(parsed.values) == 2:
            root, clip_id = Path(parsed.values[0]), parsed.values[1]
        else:
            console.error("library info expects [DIR] CLIP_ID")
            return 2
        record = find_clip(root, clip_id)
        value = record_to_dict(record)
        if parsed.json:
            console.print(json.dumps(value, ensure_ascii=False, indent=2))
        else:
            for key, item in value.items():
                console.print(f"{key.replace('_', ' ').title()}: {item}")
        return 0
    except (CatalogError, SemanticError) as err:
        console.error(str(err))
        return 1


def _print_library_table(records, console: Console) -> None:
    """Print a compact dependency-free table for human library listings."""
    headers = ("ID", "PLATFORM", "AUTHOR", "LIKES", "VIEWS", "STATUS", "PATH")
    rows = [
        (
            record.clip_id,
            record.platform,
            record.author or "?",
            str(record.likes) if record.likes is not None else "?",
            str(record.views) if record.views is not None else "?",
            "present" if record.available else "missing",
            record.relative_path,
        )
        for record in records
    ]
    widths = [max([len(headers[i]), *(len(row[i]) for row in rows)]) for i in range(len(headers))]
    console.print("  ".join(value.ljust(widths[i]) for i, value in enumerate(headers)))
    for row in rows:
        console.print("  ".join(value.ljust(widths[i]) for i, value in enumerate(row)))


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    console = Console()

    if args and args[0] == "watch":
        console.banner(__version__)
        console.dim("Personal use only — respect creators and platform Terms of Use.")
        return _run_watch(args[1:], console)

    if args and args[0] == "library":
        if "--json" not in args and not any(value in args for value in ("-h", "--help")):
            console.banner(__version__)
        return _run_library(args[1:], console)

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
    browser = opts.import_cookies
    if not browser:
        return None

    def prepare(context) -> None:
        from clipfetch.cookies import CookieImportError, import_session_cookies

        try:
            cookies = import_session_cookies(platform, browser)
            context.add_cookies(cookies)
            console.success(
                f"Imported {len(cookies)} {platform.label} cookie(s) from {browser}."
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
    from clipfetch.downloader import DownloadPool, existing_idents
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
        with session.platform_session(
            platform, console, headed=opts.headed, prepare=prepare
        ) as context:
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
    already_have = existing_idents(opts.out, noun)
    if already_have:
        console.info(f"Skipping {len(already_have)} {noun}(s) already in {opts.out}.")

    started = time.monotonic()
    with session.platform_session(
        platform, console, headed=opts.headed, prepare=prepare
    ) as context:
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
            results = browser_download.download_all(
                context, found, opts.out, noun, console, metadata=opts.metadata
            )
        else:
            headers = {"Cookie": session.cookie_header(context, platform)}
            with MultiProgress(console, opts.count, noun=noun) as progress:
                pool = DownloadPool(
                    opts.out, noun, opts.workers, progress,
                    extra_headers=headers, metadata=opts.metadata,
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
        elif result.catalog_error:
            console.error(
                f"Catalog warning for {result.clip.ident}: {result.catalog_error}. "
                f"The video is safe; retry with 'clipfetch library index {opts.out}'."
            )
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
