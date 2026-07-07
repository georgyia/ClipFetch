import io
import sys

from clipfetch.ui import Console
from clipfetch.watcher import find_videos, player_command, watch


def _console():
    return Console(io.StringIO())


def test_find_videos_filters_and_sorts(tmp_path):
    (tmp_path / "reel_002_B.mp4").write_bytes(b"x")
    (tmp_path / "reel_001_A.mov").write_bytes(b"x")
    (tmp_path / "notes.txt").write_bytes(b"x")
    (tmp_path / "thumb.jpg").write_bytes(b"x")
    assert [p.name for p in find_videos(tmp_path)] == ["reel_001_A.mov", "reel_002_B.mp4"]


def test_watch_plays_each_in_order(tmp_path):
    for name in ["reel_001_A.mp4", "reel_002_B.mp4", "reel_003_C.mp4"]:
        (tmp_path / name).write_bytes(b"x")
    played = []
    code = watch(tmp_path, _console(), runner=played.append)
    assert code == 0
    assert [p.name for p in played] == ["reel_001_A.mp4", "reel_002_B.mp4", "reel_003_C.mp4"]


def test_watch_shuffle_plays_all(tmp_path):
    names = {f"reel_{i}.mp4" for i in range(5)}
    for name in names:
        (tmp_path / name).write_bytes(b"x")
    played = []
    watch(tmp_path, _console(), shuffle=True, runner=played.append)
    assert {p.name for p in played} == names


def test_watch_empty_and_missing(tmp_path):
    assert watch(tmp_path, _console(), runner=lambda p: None) == 1  # empty folder
    assert watch(tmp_path / "nope", _console(), runner=lambda p: None) == 1


def test_player_command_is_platform_appropriate(tmp_path):
    video = tmp_path / "v.mp4"
    cmd = player_command(video)
    assert str(video) in cmd
    if sys.platform == "darwin":
        assert cmd[:2] == ["open", "-W"]
