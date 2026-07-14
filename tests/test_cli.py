import json
from pathlib import Path

import pytest

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
