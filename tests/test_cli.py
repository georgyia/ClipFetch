from pathlib import Path

import pytest

from clipfetch.cli import MAX_WORKERS, main, parse_args


def test_parse_reels_count():
    opts = parse_args(["-reels", "25"])
    assert opts.reels == 25
    assert opts.out == Path("reels")
    assert not opts.headed
    assert not opts.dry_run


def test_workers_capped_by_reel_count():
    assert parse_args(["-reels", "3"]).workers == 3
    assert parse_args(["-reels", "100"]).workers == 8


def test_custom_out_and_flags():
    opts = parse_args(["-reels", "5", "--out", "clips", "--headed", "--dry-run"])
    assert opts.out == Path("clips")
    assert opts.headed
    assert opts.dry_run


@pytest.mark.parametrize("argv", [
    [],                       # no action given
    ["-reels", "0"],          # below minimum
    ["-reels", "abc"],        # not a number
    ["-reels", "5", "--workers", str(MAX_WORKERS + 1)],
])
def test_invalid_invocations_exit(argv):
    with pytest.raises(SystemExit):
        parse_args(argv)


def test_main_returns_nonzero_on_bad_args(capsys):
    assert main([]) != 0
    assert "clipfetch -reels 25" in capsys.readouterr().err


def test_main_version(capsys):
    assert main(["--version"]) == 0
