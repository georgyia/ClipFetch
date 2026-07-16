"""Command-line entry point for ClipFetch."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from clipfetch import __version__, platforms
from clipfetch.errors import ClipFetchError
from clipfetch.library import ClipFilter, evaluate_filter, parse_magnitude
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
    filters: ClipFilter
    scan_limit: int


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


def _magnitude(value: str) -> int:
    try:
        return parse_magnitude(value)
    except ValueError as err:
        raise argparse.ArgumentTypeError(str(err)) from err


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
    parser.add_argument("--min-likes", type=_magnitude, help="accept clips at/above this count")
    parser.add_argument("--max-likes", type=_magnitude, help="accept clips at/below this count")
    parser.add_argument("--min-views", type=_magnitude, help="accept clips at/above this count")
    parser.add_argument("--max-views", type=_magnitude, help="accept clips at/below this count")
    parser.add_argument(
        "--author", action="append", default=[], help="accepted author (repeatable)"
    )
    parser.add_argument(
        "--hashtag", action="append", default=[], help="required hashtag (repeatable)"
    )
    parser.add_argument("--topic", action="append", default=[], help="local topic (repeatable)")
    parser.add_argument(
        "--scan-limit",
        type=_positive_int,
        help="maximum unique feed candidates (default: max(100, COUNT*10))",
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
        filters=ClipFilter(
            min_likes=args.min_likes,
            max_likes=args.max_likes,
            min_views=args.min_views,
            max_views=args.max_views,
            authors=tuple(args.author),
            hashtags=tuple(args.hashtag),
            platforms=(platform.key,),
            topics=tuple(args.topic),
        ),
        scan_limit=args.scan_limit or max(100, count * 10),
    )


def _run_watch(args: list[str], console: Console) -> int:
    from clipfetch.watcher import watch

    parser = argparse.ArgumentParser(prog="clipfetch watch")
    parser.add_argument(
        "dir",
        nargs="?",
        default="reels",
        type=Path,
        help="folder of downloaded clips (default: ./reels)",
    )
    parser.add_argument("--shuffle", action="store_true", help="play in random order")
    parser.add_argument("--collection")
    parser.add_argument("--min-likes")
    parser.add_argument("--max-likes")
    parser.add_argument("--min-views")
    parser.add_argument("--max-views")
    parser.add_argument("--author", action="append", default=[])
    parser.add_argument("--hashtag", action="append", default=[])
    parser.add_argument("--platform", action="append", default=[])
    parser.add_argument("--topic", action="append", default=[])
    try:
        parsed = parser.parse_args(args)
    except SystemExit as exit_:
        return int(exit_.code or 0)
    direct = any(
        (
            parsed.min_likes,
            parsed.max_likes,
            parsed.min_views,
            parsed.max_views,
            parsed.author,
            parsed.hashtag,
            parsed.platform,
            parsed.topic,
        )
    )
    if parsed.collection and direct:
        console.error("--collection cannot be combined with direct filters")
        return 2
    if not parsed.collection and not direct:
        return watch(parsed.dir, console, shuffle=parsed.shuffle)
    from clipfetch.catalog import CatalogError
    from clipfetch.collections import CollectionError, get_collection
    from clipfetch.library import ClipFilter, parse_magnitude, query_library

    try:
        filters = (
            get_collection(parsed.dir, parsed.collection).filters
            if parsed.collection
            else ClipFilter(
                min_likes=parse_magnitude(parsed.min_likes) if parsed.min_likes else None,
                max_likes=parse_magnitude(parsed.max_likes) if parsed.max_likes else None,
                min_views=parse_magnitude(parsed.min_views) if parsed.min_views else None,
                max_views=parse_magnitude(parsed.max_views) if parsed.max_views else None,
                authors=tuple(parsed.author),
                hashtags=tuple(parsed.hashtag),
                platforms=tuple(parsed.platform),
                topics=tuple(parsed.topic),
            )
        )
        result = query_library(parsed.dir, filters)
    except (CatalogError, CollectionError, ValueError) as err:
        console.error(str(err))
        return 1
    videos = [parsed.dir / record.relative_path for record in result.clips]
    return watch(parsed.dir, console, shuffle=parsed.shuffle, videos=videos)


def _run_topics(args: list[str], console: Console) -> int:
    from clipfetch.topics import (
        TopicError,
        add_topic,
        init_topics,
        load_topics,
        remove_topic,
    )

    parser = argparse.ArgumentParser(prog="clipfetch topics")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "list"):
        child = commands.add_parser(command)
        child.add_argument("dir", nargs="?", default="reels", type=Path)
    add_parser = commands.add_parser("add")
    add_parser.add_argument("values", nargs="+", metavar="[DIR] NAME")
    add_parser.add_argument("--description", required=True)
    add_parser.add_argument("--example", action="append", required=True)
    remove_parser = commands.add_parser("remove")
    remove_parser.add_argument("values", nargs="+", metavar="[DIR] NAME")
    try:
        parsed = parser.parse_args(args)
    except SystemExit as exit_:
        return int(exit_.code or 0)
    try:
        if parsed.command == "init":
            config = init_topics(parsed.dir)
            console.success(f"Initialized {len(config.topics)} topics in {parsed.dir}.")
            return 0
        if parsed.command == "list":
            config = load_topics(parsed.dir)
            for topic in config.topics:
                console.print(f"{topic.name}: {topic.description}")
            console.info(f"{len(config.topics)} topic(s); threshold {config.threshold:.2f}.")
            return 0
        if len(parsed.values) == 1:
            root, name = Path("reels"), parsed.values[0]
        elif len(parsed.values) == 2:
            root, name = Path(parsed.values[0]), parsed.values[1]
        else:
            console.error(f"topics {parsed.command} expects [DIR] NAME")
            return 2
        if parsed.command == "add":
            topic = add_topic(root, name, parsed.description, parsed.example)
            console.success(f"Added topic {topic.name}.")
        else:
            remove_topic(root, name)
            console.success(f"Removed topic {name}.")
        return 0
    except TopicError as err:
        console.error(str(err))
        return 1


def _run_library(args: list[str], console: Console) -> int:
    """Dispatch catalog maintenance commands without importing browser code."""
    from clipfetch.catalog import CatalogError, index_library
    from clipfetch.collections import CollectionError
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
    from clipfetch.topics import TopicError
    from clipfetch.transcription import TranscriptionError

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
    list_parser.add_argument("--topic", action="append", default=[])
    list_parser.add_argument("--downloaded-after", type=date_value)
    list_parser.add_argument("--downloaded-before", type=date_value)
    list_parser.add_argument("--sort", choices=["likes", "views", "date", "author"], default="date")
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
    search_parser.add_argument("--topic", action="append", default=[])
    search_parser.add_argument("--downloaded-after", type=date_value)
    search_parser.add_argument("--downloaded-before", type=date_value)
    search_parser.add_argument("--limit", type=_positive_int, default=20)
    search_parser.add_argument("--json", action="store_true")
    categorize_parser = commands.add_parser(
        "categorize", help="assign local user-defined topics to clips"
    )
    categorize_parser.add_argument("dir", nargs="?", default="reels", type=Path)
    tag_parser = commands.add_parser("tag", help="manually add/remove a clip topic")
    tag_parser.add_argument("values", nargs="+", metavar="[DIR] CLIP_ID")
    tag_parser.add_argument("--topic", required=True)
    tag_parser.add_argument("--remove", action="store_true")
    collection_parser = commands.add_parser("collection", help="manage saved collections")
    collection_commands = collection_parser.add_subparsers(dest="collection_command", required=True)
    collection_save = collection_commands.add_parser("save")
    collection_save.add_argument("values", nargs="+", metavar="[DIR] NAME")
    collection_save.add_argument("--min-likes", type=magnitude)
    collection_save.add_argument("--max-likes", type=magnitude)
    collection_save.add_argument("--min-views", type=magnitude)
    collection_save.add_argument("--max-views", type=magnitude)
    collection_save.add_argument("--author", action="append", default=[])
    collection_save.add_argument("--hashtag", action="append", default=[])
    collection_save.add_argument("--platform", action="append", default=[])
    collection_save.add_argument("--topic", action="append", default=[])
    collection_save.add_argument("--downloaded-after", type=date_value)
    collection_save.add_argument("--downloaded-before", type=date_value)
    collection_list = collection_commands.add_parser("list")
    collection_list.add_argument("dir", nargs="?", default="reels", type=Path)
    for command in ("show", "delete"):
        child = collection_commands.add_parser(command)
        child.add_argument("values", nargs="+", metavar="[DIR] NAME")
    export_parser = commands.add_parser("export", help="export a dynamic collection")
    export_parser.add_argument("dir", nargs="?", default="reels", type=Path)
    export_parser.add_argument("--collection", required=True)
    export_parser.add_argument("--format", choices=["m3u", "json"], required=True)
    export_parser.add_argument("--out", type=Path)
    enrich_parser = commands.add_parser("enrich", help="add optional local enrichments")
    enrich_commands = enrich_parser.add_subparsers(dest="enrich_command", required=True)
    transcript_parser = enrich_commands.add_parser("transcript")
    transcript_parser.add_argument("dir", nargs="?", default="reels", type=Path)
    transcript_parser.add_argument("--model", default="base")
    transcript_parser.add_argument("--force", action="store_true")
    transcript_parser.add_argument("--min-likes", type=magnitude)
    transcript_parser.add_argument("--max-likes", type=magnitude)
    transcript_parser.add_argument("--min-views", type=magnitude)
    transcript_parser.add_argument("--max-views", type=magnitude)
    transcript_parser.add_argument("--author", action="append", default=[])
    transcript_parser.add_argument("--hashtag", action="append", default=[])
    transcript_parser.add_argument("--platform", action="append", default=[])
    transcript_parser.add_argument("--topic", action="append", default=[])
    transcript_parser.add_argument("--downloaded-after", type=date_value)
    transcript_parser.add_argument("--downloaded-before", type=date_value)
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
                topics=tuple(parsed.topic),
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
                console.print(json.dumps(query_to_dict(list_result), ensure_ascii=False, indent=2))
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
                topics=tuple(parsed.topic),
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
        if parsed.command == "categorize":
            from clipfetch.semantic import FastEmbedder
            from clipfetch.topics import categorize_library

            category_report = categorize_library(parsed.dir, FastEmbedder())
            console.success(
                f"Categorized {category_report.categorized} clip(s); "
                f"{category_report.unchanged} unchanged, "
                f"{category_report.uncategorized} uncategorized."
            )
            return 0
        if parsed.command == "tag":
            from clipfetch.topics import tag_clip

            if len(parsed.values) == 1:
                root, clip_id = Path("reels"), parsed.values[0]
            elif len(parsed.values) == 2:
                root, clip_id = Path(parsed.values[0]), parsed.values[1]
            else:
                console.error("library tag expects [DIR] CLIP_ID")
                return 2
            tag_clip(root, clip_id, parsed.topic, remove=parsed.remove)
            verb = "Removed" if parsed.remove else "Assigned"
            console.success(f"{verb} topic {parsed.topic} for {clip_id}.")
            return 0
        if parsed.command == "collection":
            from clipfetch.collections import (
                collection_to_dict,
                delete_collection,
                get_collection,
                load_collections,
                resolve_collection,
                save_collection,
            )

            if parsed.collection_command == "list":
                for item in load_collections(parsed.dir):
                    console.print(item.name)
                return 0
            if len(parsed.values) == 1:
                root, name = Path("reels"), parsed.values[0]
            elif len(parsed.values) == 2:
                root, name = Path(parsed.values[0]), parsed.values[1]
            else:
                console.error(f"library collection {parsed.collection_command} expects [DIR] NAME")
                return 2
            if parsed.collection_command == "save":
                filters = ClipFilter(
                    min_likes=parsed.min_likes,
                    max_likes=parsed.max_likes,
                    min_views=parsed.min_views,
                    max_views=parsed.max_views,
                    authors=tuple(parsed.author),
                    hashtags=tuple(parsed.hashtag),
                    platforms=tuple(parsed.platform),
                    topics=tuple(parsed.topic),
                    downloaded_after=parsed.downloaded_after,
                    downloaded_before=parsed.downloaded_before,
                )
                saved = save_collection(root, name, filters)
                console.success(f"Saved collection {saved.name}.")
            elif parsed.collection_command == "delete":
                delete_collection(root, name)
                console.success(f"Deleted collection {name}.")
            else:
                saved = get_collection(root, name)
                result = resolve_collection(root, name)
                console.print(json.dumps(collection_to_dict(saved), indent=2))
                _print_library_table(result.clips, console)
                console.info(f"{result.matched} current member(s).")
            return 0
        if parsed.command == "export":
            from clipfetch.collections import export_json, export_m3u, resolve_collection

            result = resolve_collection(parsed.dir, parsed.collection)
            output = (
                export_json(parsed.dir, result) if parsed.format == "json" else export_m3u(result)
            )
            if parsed.out:
                parsed.out.write_text(output, encoding="utf-8")
                console.success(f"Exported {len(result.clips)} clip(s) to {parsed.out}.")
            else:
                console.stream.write(output)
                console.stream.flush()
            return 0
        if parsed.command == "enrich":
            from clipfetch.transcription import (
                DEFAULT_TRANSCRIPT_CACHE,
                FasterWhisperTranscriber,
                enrich_transcripts,
            )

            filters = ClipFilter(
                min_likes=parsed.min_likes,
                max_likes=parsed.max_likes,
                min_views=parsed.min_views,
                max_views=parsed.max_views,
                authors=tuple(parsed.author),
                hashtags=tuple(parsed.hashtag),
                platforms=tuple(parsed.platform),
                topics=tuple(parsed.topic),
                downloaded_after=parsed.downloaded_after,
                downloaded_before=parsed.downloaded_before,
            )
            if not DEFAULT_TRANSCRIPT_CACHE.exists():
                console.info(
                    f"First use downloads the {parsed.model!r} transcription model to "
                    f"{DEFAULT_TRANSCRIPT_CACHE}; media and text stay local."
                )
            transcriber = FasterWhisperTranscriber(parsed.model)

            def transcript_progress(index, total, status, record) -> None:
                console.dim(f"  [{index}/{total}] {record.clip_id}: {status}")

            report = enrich_transcripts(
                parsed.dir,
                transcriber,
                filters,
                force=parsed.force,
                on_progress=transcript_progress,
            )
            console.success(
                f"Transcripts: {report.completed} completed, {report.skipped} skipped, "
                f"{report.silent} silent, {report.unsupported} unsupported, "
                f"{report.failed} failed."
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
        from clipfetch.topics import assignment_details, topics_path

        value["topics"] = (
            assignment_details(root, record.platform, record.clip_id)
            if topics_path(root).exists()
            else []
        )
        if parsed.json:
            console.print(json.dumps(value, ensure_ascii=False, indent=2))
        else:
            for key, item in value.items():
                console.print(f"{key.replace('_', ' ').title()}: {item}")
        return 0
    except (
        CatalogError,
        CollectionError,
        SemanticError,
        TopicError,
        TranscriptionError,
    ) as err:
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
        machine_export = len(args) > 1 and args[1] == "export" and "--out" not in args
        if (
            "--json" not in args
            and not machine_export
            and not any(value in args for value in ("-h", "--help"))
        ):
            console.banner(__version__)
        return _run_library(args[1:], console)

    if args and args[0] == "topics":
        if not any(value in args for value in ("-h", "--help")):
            console.banner(__version__)
        return _run_topics(args[1:], console)

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
            console.success(f"Imported {len(cookies)} {platform.label} cookie(s) from {browser}.")
        except CookieImportError as err:
            console.error(f"Cookie import failed: {err}")
            console.info("Falling back to ClipFetch's own sign-in.")

    return prepare


def _selection_for(opts: Options):
    """Build a side-effect-free feed-candidate selector."""
    from clipfetch.catalog import CatalogRecord

    topic_matcher = None
    if opts.filters.topics:
        from clipfetch.semantic import FastEmbedder
        from clipfetch.topics import TopicMatcher

        topic_matcher = TopicMatcher(opts.out, FastEmbedder())

    def select(clip):
        record = CatalogRecord(
            platform=clip.platform,
            clip_id=clip.ident,
            relative_path="",
            file_size=0,
            file_mtime_ns=0,
            downloaded_at="",
            source_url=clip.url,
            author=clip.author,
            caption=clip.caption,
            likes=clip.likes,
            metadata_state="candidate",
            hashtags=clip.normalized_metadata().hashtags,
            views=clip.views,
            comments_count=clip.comments_count,
            shares=clip.shares,
            duration_seconds=clip.duration_seconds,
        )
        topics = topic_matcher.topics_for(clip) if topic_matcher else ()
        return evaluate_filter(record, opts.filters, topics)

    return select


def _selection_summary(stats, console: Console) -> None:
    rejected = (
        ", ".join(f"{name}={count}" for name, count in sorted(stats.rejected_by.items())) or "none"
    )
    reason = " (scan limit reached)" if stats.stopped_by_scan_limit else ""
    console.info(
        f"Selection: {stats.scanned} scanned, {stats.accepted} accepted, "
        f"{stats.rejected} rejected [{rejected}], "
        f"{stats.unknown_required_metadata} unknown-required{reason}."
    )


def _has_selection_filters(filters: ClipFilter) -> bool:
    return (
        filters.min_likes is not None
        or filters.max_likes is not None
        or filters.min_views is not None
        or filters.max_views is not None
        or bool(filters.authors or filters.hashtags or filters.topics)
    )


def _run(opts: Options, console: Console) -> None:
    """Collect clips from the feed and download them as they are found."""
    import time

    # Imported lazily so --help and unit tests never need the browser stack.
    from clipfetch import collector, session
    from clipfetch.collector import SelectionStats
    from clipfetch.downloader import DownloadPool, existing_idents
    from clipfetch.errors import DownloadError
    from clipfetch.ui import MultiProgress, Spinner, human_size

    platform = opts.platform
    noun = platform.noun
    source = f"@{opts.target}" if opts.target else f"your {platform.label} feed"
    console.info(f"Source: {source}")

    prepare = _cookie_importer(opts, platform, console)
    selector = _selection_for(opts)
    selection_stats = SelectionStats()
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
                    context,
                    platform,
                    opts.quality,
                    opts.count,
                    on_clip=lambda clip: None,
                    target=opts.target,
                    on_progress=lambda n: spinner.update(f"Collecting {noun}s… {n}/{opts.count}"),
                    scan_limit=opts.scan_limit,
                    selector=selector,
                    selection_stats=selection_stats,
                )
        console.success(f"Collected {len(found)} of {opts.count} {noun}(s).")
        for clip in found:
            console.print(f"  {clip.ident}  {clip.video_url}")
        _selection_summary(selection_stats, console)
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
                    context,
                    platform,
                    opts.quality,
                    opts.count,
                    on_clip=lambda clip: None,
                    target=opts.target,
                    already_have=already_have,
                    on_progress=lambda n: spinner.update(f"Collecting {noun}s… {n}/{opts.count}"),
                    scan_limit=opts.scan_limit,
                    selector=selector,
                    selection_stats=selection_stats,
                )
            console.info(f"Downloading {len(found)} {noun}(s) through the browser…")
            results = browser_download.download_all(
                context, found, opts.out, noun, console, metadata=opts.metadata
            )
        else:
            headers = {"Cookie": session.cookie_header(context, platform)}
            with MultiProgress(console, opts.count, noun=noun) as progress:
                pool = DownloadPool(
                    opts.out,
                    noun,
                    opts.workers,
                    progress,
                    extra_headers=headers,
                    metadata=opts.metadata,
                )
                found = collector.collect(
                    context,
                    platform,
                    opts.quality,
                    opts.count,
                    on_clip=pool.submit,
                    target=opts.target,
                    already_have=already_have,
                    on_progress=lambda n: progress.set_status(
                        f"Collecting {noun}s… {n}/{opts.count}"
                    ),
                    scan_limit=opts.scan_limit,
                    selector=selector,
                    selection_stats=selection_stats,
                )
                progress.set_status("Feed done — finishing downloads…")
                results = pool.wait()
                progress.set_status("")
    elapsed = time.monotonic() - started
    _selection_summary(selection_stats, console)

    downloaded = [r for r in results if r.ok]
    failed_count = sum(not result.ok for result in results)
    console.info(
        f"Outcome: {selection_stats.accepted} accepted, "
        f"{len(downloaded)} downloaded, {failed_count} failed."
    )
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
        if selection_stats.accepted == 0 and _has_selection_filters(opts.filters):
            console.info("No feed candidates matched the requested filters.")
            return
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
