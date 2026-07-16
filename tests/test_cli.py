import json
from contextlib import contextmanager
from pathlib import Path

import pytest

from clipfetch.catalog import Catalog
from clipfetch.cli import MAX_WORKERS, main, parse_args
from clipfetch.model import Quality


def test_parse_reels_count():
    opts = parse_args(["-reels", "25"])
    assert opts.platform.key == "instagram"
    assert opts.count == 25
    assert opts.out == Path("reels")
    assert opts.quality is Quality.HIGH
    assert not opts.headed
    assert not opts.dry_run


def test_workers_capped_by_count():
    assert parse_args(["-reels", "3"]).workers == 3
    assert parse_args(["-reels", "100"]).workers == 8


def test_account_target_is_parsed_and_stripped():
    assert parse_args(["-reels", "10"]).target is None
    assert parse_args(["-reels", "10", "@nasa"]).target == "nasa"
    assert parse_args(["-reels", "10", "nasa"]).target == "nasa"


def test_custom_out_quality_and_flags():
    opts = parse_args(
        ["-reels", "5", "--out", "clips", "--quality", "low", "--headed", "--dry-run"]
    )
    assert opts.out == Path("clips")
    assert opts.quality is Quality.LOW
    assert opts.headed
    assert opts.dry_run
    assert not opts.metadata  # off unless asked for


def test_metadata_flag():
    assert parse_args(["-reels", "5", "--metadata"]).metadata
    assert not parse_args(["-reels", "5"]).metadata


def test_download_filters_and_default_scan_limit():
    opts = parse_args(
        [
            "-reels",
            "25",
            "--min-likes",
            "1m",
            "--author",
            "nasa",
            "--author",
            "spacex",
            "--topic",
            "entrepreneurship",
        ]
    )
    assert opts.filters.min_likes == 1_000_000
    assert opts.filters.authors == ("nasa", "spacex")
    assert opts.filters.topics == ("entrepreneurship",)
    assert opts.scan_limit == 250
    assert parse_args(["-reels", "3"]).scan_limit == 100
    assert parse_args(["-reels", "3", "--scan-limit", "7"]).scan_limit == 7


@pytest.mark.parametrize("browser", ["chrome", "firefox", "safari"])
def test_cookie_import_browser_choices(browser):
    assert parse_args(["-reels", "5", "--import-cookies", browser]).import_cookies == browser


@pytest.mark.parametrize("argv", [
    [],                       # no source given
    ["-reels", "0"],          # below minimum
    ["-reels", "abc"],        # not a number
    ["-reels", "5", "--workers", str(MAX_WORKERS + 1)],
    ["-reels", "5", "--quality", "ultra"],  # invalid choice
])
def test_invalid_invocations_exit(argv):
    with pytest.raises(SystemExit):
        parse_args(argv)


def test_main_returns_nonzero_on_bad_args(capsys):
    assert main([]) != 0
    assert "nothing to do" in capsys.readouterr().err


def test_main_version(capsys):
    assert main(["--version"]) == 0


def test_main_version_does_not_print_banner(capsys):
    assert main(["--version"]) == 0
    captured = capsys.readouterr()
    assert "ClipFetch" not in captured.out


def test_main_help_does_not_print_banner(capsys):
    assert main(["--help"]) == 0
    captured = capsys.readouterr()
    assert "ClipFetch" not in captured.out
    assert "usage:" in captured.out


def test_main_prints_banner_for_valid_run(capsys, monkeypatch):
    # Avoid actually launching a browser/download by mocking _run.
    from clipfetch import cli

    calls = []

    def fake_run(opts, console):
        calls.append(opts)

    monkeypatch.setattr(cli, "_run", fake_run)
    assert main(["-reels", "1"]) == 0
    assert "ClipFetch" in capsys.readouterr().out
    assert len(calls) == 1


def test_library_index_cli_reports_counts(tmp_path, capsys):
    (tmp_path / "reel_001_ABC.mp4").write_bytes(b"video")
    assert main(["library", "index", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "1 scanned" in output
    assert "1 inserted" in output


def test_library_index_missing_directory_is_nonzero(tmp_path, capsys):
    assert main(["library", "index", str(tmp_path / "missing")]) == 1
    assert "does not exist" in capsys.readouterr().out


def test_library_list_json_has_no_banner_or_ansi_and_filters(tmp_path, capsys):
    video = tmp_path / "reel_001_ABC.mp4"
    video.write_bytes(b"video")
    video.with_suffix(".json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "platform": "instagram",
                "id": "ABC",
                "author": "nasa",
                "caption": "Build #Entrepreneurship",
                "likes": 1_500_000,
                "hashtags": ["entrepreneurship"],
                "views": 10_000_000,
            }
        ),
        encoding="utf-8",
    )
    assert main(["library", "index", str(tmp_path)]) == 0
    capsys.readouterr()
    assert main(
        [
            "library",
            "list",
            str(tmp_path),
            "--min-likes",
            "1m",
            "--hashtag",
            "entrepreneurship",
            "--json",
        ]
    ) == 0
    output = capsys.readouterr().out
    assert "ClipFetch" not in output and "\x1b[" not in output
    value = json.loads(output)
    assert value["matched"] == 1
    assert value["clips"][0]["id"] == "ABC"


def test_library_info_and_human_summary(tmp_path, capsys):
    video = tmp_path / "reel_001_ABC.mp4"
    video.write_bytes(b"video")
    assert main(["library", "index", str(tmp_path)]) == 0
    capsys.readouterr()

    assert main(["library", "list", str(tmp_path), "--min-likes", "1m"]) == 0
    output = capsys.readouterr().out
    assert "0 matched" in output and "1 lacked required metadata" in output

    assert main(["library", "info", str(tmp_path), "ABC", "--json"]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["id"] == "ABC" and info["available"] is True


def test_library_list_invalid_number_and_missing_clip_exit_nonzero(tmp_path, capsys):
    assert main(["library", "list", str(tmp_path), "--min-likes", "-1"]) == 2
    assert main(["library", "info", str(tmp_path), "NOPE"]) == 1
    assert "not found" in capsys.readouterr().out


def test_semantic_cli_uses_local_index_and_json_has_no_banner(tmp_path, capsys, monkeypatch):
    video = tmp_path / "reel_001_ABC.mp4"
    video.write_bytes(b"video")
    video.with_suffix(".json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "platform": "instagram",
                "id": "ABC",
                "caption": "startup advice",
                "hashtags": ["entrepreneurship"],
                "likes": 2_000_000,
            }
        ),
        encoding="utf-8",
    )
    assert main(["library", "index", str(tmp_path)]) == 0
    capsys.readouterr()

    class Fake:
        model_id = "test/model"
        revision = "v1"

        def embed(self, texts):
            return [[1.0, 0.0] if "startup" in text else [0.9, 0.1] for text in texts]

    from clipfetch import semantic

    monkeypatch.setattr(semantic, "FastEmbedder", Fake)
    assert main(["library", "semantic-index", str(tmp_path)]) == 0
    assert "1 indexed" in capsys.readouterr().out

    assert main(
        [
            "library",
            "search",
            str(tmp_path),
            "entrepreneurship",
            "--min-likes",
            "1m",
            "--json",
        ]
    ) == 0
    output = capsys.readouterr().out
    assert "ClipFetch" not in output and "\x1b[" not in output
    value = json.loads(output)
    assert value["matches"][0]["clip"]["id"] == "ABC"
    assert value["matches"][0]["score"] > 0.9


def test_topics_cli_init_add_manual_tag_and_filter(tmp_path, capsys):
    video = tmp_path / "reel_001_ABC.mp4"
    video.write_bytes(b"video")
    assert main(["library", "index", str(tmp_path)]) == 0
    assert main(["topics", "init", str(tmp_path)]) == 0
    assert main(
        [
            "topics",
            "add",
            str(tmp_path),
            "climate-tech",
            "--description",
            "clean technology",
            "--example",
            "renewable energy",
        ]
    ) == 0
    assert main(
        ["library", "tag", str(tmp_path), "ABC", "--topic", "climate-tech"]
    ) == 0
    capsys.readouterr()
    assert main(
        ["library", "list", str(tmp_path), "--topic", "climate-tech", "--json"]
    ) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["matched"] == 1 and result["clips"][0]["id"] == "ABC"


def test_collection_cli_save_show_export_and_filtered_watch(tmp_path, capsys, monkeypatch):
    video = tmp_path / "reel_001_ABC.mp4"
    video.write_bytes(b"video")
    video.with_suffix(".json").write_text(
        json.dumps({"platform": "instagram", "id": "ABC", "likes": 2_000_000}),
        encoding="utf-8",
    )
    assert main(["library", "index", str(tmp_path)]) == 0
    assert main(
        [
            "library",
            "collection",
            "save",
            str(tmp_path),
            "viral",
            "--min-likes",
            "1m",
        ]
    ) == 0
    capsys.readouterr()
    assert main(
        ["library", "export", str(tmp_path), "--collection", "viral", "--format", "m3u"]
    ) == 0
    assert capsys.readouterr().out == "#EXTM3U\nreel_001_ABC.mp4\n"

    captured = []

    def fake_watch(directory, console, **kwargs):
        captured.extend(kwargs["videos"])
        return 0

    from clipfetch import watcher

    monkeypatch.setattr(watcher, "watch", fake_watch)
    assert main(["watch", str(tmp_path), "--collection", "viral"]) == 0
    assert captured == [video]


def test_transcript_enrichment_cli_with_fake_backend(tmp_path, capsys, monkeypatch):
    video = tmp_path / "reel_001_ABC.mp4"
    video.write_bytes(b"video")
    assert main(["library", "index", str(tmp_path)]) == 0

    class Fake:
        model_id = "fake/base"
        revision = "v1"

        def __init__(self, model):
            self.model_id = "fake/" + model

        def transcribe(self, path):
            from clipfetch.transcription import TranscriptResult

            return TranscriptResult("spoken startup advice", "en")

    from clipfetch import transcription

    monkeypatch.setattr(transcription, "FasterWhisperTranscriber", Fake)
    capsys.readouterr()
    assert main(["library", "enrich", "transcript", str(tmp_path), "--model", "base"]) == 0
    assert "1 completed" in capsys.readouterr().out
    with Catalog.open(tmp_path) as catalog:
        assert catalog.get("instagram", "ABC").transcript_text == "spoken startup advice"


def test_comment_enrichment_and_purge_cli_with_fake_browser(tmp_path, capsys, monkeypatch):
    video = tmp_path / "reel_001_ABC.mp4"
    video.write_bytes(b"video")
    video.with_suffix(".json").write_text(
        json.dumps({"platform": "instagram", "id": "ABC", "likes": 10}),
        encoding="utf-8",
    )
    assert main(["library", "index", str(tmp_path)]) == 0

    from clipfetch import comments, session

    events = []
    original_select = comments.select_comment_records
    original_limiter = comments.RequestLimiter

    def tracked_select(root, filters):
        events.append("select")
        return original_select(root, filters)

    @contextmanager
    def fake_session(*args, **kwargs):
        events.append("session")
        yield object()

    class FakeBackend:
        def __init__(self, context):
            pass

        def resolve_media_id(self, record):
            return "99"

        def fetch_page(self, media_id, cursor, limit):
            return comments.CommentPage((comments.CommentItem("1", "useful context"),))

    monkeypatch.setattr(comments, "select_comment_records", tracked_select)
    monkeypatch.setattr(comments, "InstagramCommentBackend", FakeBackend)
    monkeypatch.setattr(
        comments,
        "RequestLimiter",
        lambda: original_limiter(interval=0),
    )
    monkeypatch.setattr(session, "platform_session", fake_session)
    capsys.readouterr()
    assert main(
        [
            "library",
            "enrich",
            "comments",
            str(tmp_path),
            "--max-comments",
            "1",
            "--min-likes",
            "5",
        ]
    ) == 0
    assert events == ["select", "session"]
    assert "1 completed" in capsys.readouterr().out
    with Catalog.open(tmp_path) as catalog:
        assert catalog.get("instagram", "ABC").comment_text == "useful context"

    assert main(["library", "purge-comments", str(tmp_path)]) == 0
    assert "1 clip(s)" in capsys.readouterr().out
    with Catalog.open(tmp_path) as catalog:
        assert catalog.get("instagram", "ABC").comment_text is None
