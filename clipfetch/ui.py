"""Hand-rolled interactive terminal UI: colors, spinner, and live progress bars.

Built on raw ANSI escape codes on purpose — ClipFetch keeps its dependency
footprint to the browser driver only. Everything degrades gracefully to plain
text when stdout is not a TTY or ``NO_COLOR`` is set.
"""

from __future__ import annotations

import itertools
import os
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
RED = "\x1b[31m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
MAGENTA = "\x1b[35m"
CYAN = "\x1b[36m"

_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_HIDE_CURSOR = "\x1b[?25l"
_SHOW_CURSOR = "\x1b[?25h"
_CLEAR_LINE = "\x1b[2K\r"


def supports_ansi(stream=None) -> bool:
    """Whether ``stream`` (default stdout) can render ANSI escapes."""
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return hasattr(stream, "isatty") and stream.isatty()


def render_bar(fraction: float, width: int = 24) -> str:
    """Render a progress bar like ``[██████░░░░]`` for a 0..1 fraction."""
    fraction = min(max(fraction, 0.0), 1.0)
    filled = round(fraction * width)
    return "█" * filled + "░" * (width - filled)


def human_size(num_bytes: float) -> str:
    """Format a byte count like ``3.4 MB``."""
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024 or unit == "GB":
            return f"{num_bytes:.1f} {unit}" if unit != "B" else f"{int(num_bytes)} B"
        num_bytes /= 1024
    raise AssertionError("unreachable")


def human_duration(seconds: float) -> str:
    """Format a rough ETA without implying sub-second precision."""
    seconds = max(0, round(seconds))
    if seconds < 60:
        return f"{seconds}s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {seconds:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m"


class Console:
    """Styled line-oriented output that degrades to plain text."""

    def __init__(self, stream=None) -> None:
        self.stream = stream or sys.stdout
        self.ansi = supports_ansi(self.stream)

    def _style(self, text: str, *codes: str) -> str:
        if not self.ansi or not codes:
            return text
        return "".join(codes) + text + RESET

    def print(self, text: str = "") -> None:
        self.stream.write(text + "\n")
        self.stream.flush()

    def banner(self, version: str) -> None:
        self.print(self._style(f"◆ ClipFetch v{version}", BOLD, MAGENTA))

    def info(self, text: str) -> None:
        self.print(f"{self._style('•', CYAN)} {text}")

    def success(self, text: str) -> None:
        self.print(f"{self._style('✔', GREEN)} {text}")

    def error(self, text: str) -> None:
        self.print(f"{self._style('✖', RED, BOLD)} {text}")

    def dim(self, text: str) -> None:
        self.print(self._style(text, DIM))

    def warning_box(self, title: str, lines: list[str]) -> None:
        """A bordered, hard-to-miss warning block."""
        width = max(len(line) for line in [title, *lines]) + 2
        top = "┌" + "─" * width + "┐"
        bottom = "└" + "─" * width + "┘"
        self.print(self._style(top, YELLOW))
        self.print(self._style(f"│ {title.ljust(width - 1)}│", YELLOW, BOLD))
        for line in lines:
            self.print(self._style(f"│ {line.ljust(width - 1)}│", YELLOW))
        self.print(self._style(bottom, YELLOW))


class Spinner:
    """A single-line spinner with a live, updatable message.

    Usage::

        with Spinner(console, "Launching browser") as spin:
            spin.update("Collecting reels… 3/25")
    """

    def __init__(self, console: Console, message: str) -> None:
        self._console = console
        self._message = message
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> Spinner:
        if self._console.ansi:
            self._console.stream.write(_HIDE_CURSOR)
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        else:
            self._console.info(self._message)
        return self

    def __exit__(self, exc_type, *_exc) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join()
            self._console.stream.write(_CLEAR_LINE + _SHOW_CURSOR)
            self._console.stream.flush()

    def update(self, message: str) -> None:
        with self._lock:
            self._message = message

    def _spin(self) -> None:
        stream = self._console.stream
        for frame in itertools.cycle(_SPINNER_FRAMES):
            if self._stop.is_set():
                return
            with self._lock:
                message = self._message
            stream.write(f"{_CLEAR_LINE}{CYAN}{frame}{RESET} {message}")
            stream.flush()
            time.sleep(0.08)


@dataclass
class _Task:
    label: str
    total: int = 0  # bytes; 0 = unknown
    done: int = 0
    transferred: int = 0
    finished: bool = False
    failed: bool = False


class MultiProgress:
    """Live multi-line progress display for parallel downloads.

    Worker threads report byte counts via :meth:`update` / :meth:`finish`;
    a render thread repaints the block in place a few times per second.
    Falls back to one plain line per finished download without a TTY.
    """

    def __init__(
        self,
        console: Console,
        overall_total: int,
        noun: str = "clip",
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._console = console
        self._overall_total = overall_total
        self._noun = noun
        self._clock = clock
        self._started_at: float | None = None
        self._tasks: dict[int, _Task] = {}
        self._status = ""
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._rendered_lines = 0

    def __enter__(self) -> MultiProgress:
        self._started_at = self._clock()
        if self._console.ansi:
            self._console.stream.write(_HIDE_CURSOR)
            self._thread = threading.Thread(target=self._render_loop, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, exc_type, *_exc) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join()
            self._render()  # final frame
            self._console.stream.write(_SHOW_CURSOR)
            self._console.stream.flush()

    def set_status(self, text: str) -> None:
        """Show a one-line status (e.g. collection progress) above the bars."""
        with self._lock:
            changed = text != self._status
            self._status = text
        if changed and not self._console.ansi:
            self._console.info(text)

    def add(self, task_id: int, label: str, total: int = 0, done: int = 0) -> None:
        with self._lock:
            self._tasks[task_id] = _Task(label, total, done)

    def update(self, task_id: int, done: int, total: int | None = None) -> None:
        with self._lock:
            task = self._tasks[task_id]
            task.transferred += max(0, done - task.done)
            task.done = done
            if total is not None:
                task.total = total

    def finish(self, task_id: int, failed: bool = False) -> None:
        with self._lock:
            task = self._tasks[task_id]
            task.finished = True
            task.failed = failed
        if not self._console.ansi:
            mark = "failed" if failed else "done"
            self._console.print(f"  {task.label}: {mark}")

    def _snapshot(self) -> list[tuple[int, _Task]]:
        with self._lock:
            return [(tid, _Task(**vars(t))) for tid, t in sorted(self._tasks.items())]

    def _render_loop(self) -> None:
        while not self._stop.wait(0.1):
            self._render()

    def _render(self) -> None:
        stream = self._console.stream
        lines = []
        tasks = self._snapshot()
        finished = sum(1 for _, t in tasks if t.finished and not t.failed)
        failed = sum(1 for _, t in tasks if t.failed)
        transferred = sum(task.transferred for _, task in tasks)
        noun = self._noun if self._overall_total == 1 else f"{self._noun}s"
        overall = (
            f"{BOLD}⇣ {finished}/{self._overall_total} {noun} downloaded"
            f" • {human_size(transferred)} transferred"
        )
        eta = self._eta(tasks, transferred)
        if eta is not None:
            overall += f" • ETA {human_duration(eta)}"
        overall += RESET
        if failed:
            overall += f" {RED}({failed} failed){RESET}"
        lines.append(overall)
        with self._lock:
            status = self._status
        if status:
            lines.append(f"  {DIM}{status}{RESET}")
        for _, task in tasks:
            if task.finished:
                continue  # keep the block compact: only active downloads
            if task.total:
                bar = render_bar(task.done / task.total, width=20)
                size = f"{human_size(task.done)} / {human_size(task.total)}"
            else:
                bar = render_bar(0, width=20)
                size = human_size(task.done)
            lines.append(f"  {CYAN}{bar}{RESET} {task.label} {DIM}{size}{RESET}")

        # Repaint in place: move up over the previous frame, clear each line.
        buffer = ""
        if self._rendered_lines:
            buffer += f"\x1b[{self._rendered_lines}F"
        for line in lines:
            buffer += f"\x1b[2K{line}\n"
        # Clear leftover lines from a taller previous frame.
        extra = self._rendered_lines - len(lines)
        if extra > 0:
            buffer += "\x1b[2K\n" * extra + f"\x1b[{extra}F"
        stream.write(buffer)
        stream.flush()
        self._rendered_lines = len(lines)

    def _eta(self, tasks: list[tuple[int, _Task]], transferred: int) -> float | None:
        """Estimate time for known remaining bytes at this run's average rate."""
        if self._started_at is None or transferred <= 0:
            return None
        elapsed = self._clock() - self._started_at
        if elapsed <= 0:
            return None
        remaining = sum(
            max(task.total - task.done, 0)
            for _, task in tasks
            if task.total and not task.finished
        )
        if remaining <= 0:
            return None
        return remaining / (transferred / elapsed)
