"""``clipfetch watch`` — play a folder of downloaded clips one after another.

Downloading is only half the point; this closes the loop by handing each video
to the operating system's default player in turn. On macOS ``open -W`` blocks
until the player quits, giving natural "next video when you close this one"
playback; other platforms open the file and move on.
"""

from __future__ import annotations

import random
import subprocess
import sys
from pathlib import Path
from typing import Callable

from clipfetch.ui import Console

VIDEO_SUFFIXES = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}


def find_videos(directory: Path) -> list[Path]:
    """Video files in ``directory``, sorted by name (download order)."""
    return sorted(
        (p for p in directory.iterdir() if p.suffix.lower() in VIDEO_SUFFIXES),
        key=lambda p: p.name,
    )


def player_command(path: Path) -> list[str]:
    """The OS command that plays ``path`` and, where possible, blocks."""
    if sys.platform == "darwin":
        return ["open", "-W", str(path)]
    if sys.platform.startswith("win"):
        return ["cmd", "/c", "start", "/wait", "", str(path)]
    return ["xdg-open", str(path)]  # Linux: best-effort, non-blocking


def _default_runner(path: Path) -> None:
    subprocess.run(player_command(path), check=False)


def watch(
    directory: Path,
    console: Console,
    shuffle: bool = False,
    runner: Callable[[Path], None] | None = None,
) -> int:
    """Play every video in ``directory`` in turn. Returns a process exit code."""
    if not directory.is_dir():
        console.error(f"Not a folder: {directory}")
        return 1
    videos = find_videos(directory)
    if not videos:
        console.error(f"No videos found in {directory}.")
        return 1
    if shuffle:
        random.shuffle(videos)

    run = runner or _default_runner
    console.info(f"Playing {len(videos)} clip(s) from {directory} — close each to advance.")
    for index, path in enumerate(videos, start=1):
        console.dim(f"  [{index}/{len(videos)}] {path.name}")
        run(path)
    console.success("Done watching.")
    return 0
