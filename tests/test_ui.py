import io

from clipfetch.ui import Console, MultiProgress, human_duration, human_size, render_bar


def test_render_bar_bounds():
    assert render_bar(0, width=10) == "░" * 10
    assert render_bar(1, width=10) == "█" * 10
    assert render_bar(2.5, width=10) == "█" * 10  # clamped
    assert render_bar(-1, width=10) == "░" * 10  # clamped


def test_render_bar_partial():
    assert render_bar(0.5, width=10) == "█" * 5 + "░" * 5


def test_human_size():
    assert human_size(512) == "512 B"
    assert human_size(2048) == "2.0 KB"
    assert human_size(5 * 1024 * 1024) == "5.0 MB"
    assert human_size(3.2 * 1024**3) == "3.2 GB"


def test_human_duration():
    assert human_duration(17.2) == "17s"
    assert human_duration(80) == "1m 20s"
    assert human_duration(3720) == "1h 02m"


def test_overall_progress_shows_transferred_bytes_and_eta():
    stream = io.StringIO()
    console = Console(stream)
    console.ansi = True
    now = {"value": 0.0}
    progress = MultiProgress(console, 2, noun="reel", clock=lambda: now["value"])
    progress._started_at = 0.0
    progress.add(1, "one.mp4", total=1000)
    progress.add(2, "two.mp4", total=1000)
    progress.update(1, 500)
    progress.update(2, 250)
    now["value"] = 10.0

    progress._render()
    output = stream.getvalue()
    assert "0/2 reels downloaded" in output
    assert "750 B transferred" in output
    assert "ETA 17s" in output


def test_resumed_bytes_are_not_counted_as_new_transfer():
    progress = MultiProgress(Console(io.StringIO()), 1)
    progress.add(1, "clip.mp4", total=1000, done=400)
    progress.update(1, 650)
    assert progress._snapshot()[0][1].transferred == 250


def test_eta_rate_window_starts_with_first_byte_not_collection():
    stream = io.StringIO()
    console = Console(stream)
    now = {"value": 0.0}
    progress = MultiProgress(console, 1, clock=lambda: now["value"])
    progress.__enter__()
    progress.add(1, "clip.mp4", total=1_000)

    now["value"] = 60.0  # feed collection delay before the download starts
    progress.update(1, 500)
    now["value"] = 70.0
    progress._render()

    assert "500 B transferred" in stream.getvalue()
    assert "ETA 10s" in stream.getvalue()


def test_warning_box_without_body_lines():
    stream = io.StringIO()
    Console(stream).warning_box("Just a title", [])
    assert "Just a title" in stream.getvalue()


def test_console_plain_without_tty():
    stream = io.StringIO()  # not a TTY -> no ANSI codes
    console = Console(stream)
    console.banner("0.1.0")
    console.success("done")
    console.warning_box("Heads up", ["line one"])
    output = stream.getvalue()
    assert "\x1b[" not in output
    assert "ClipFetch v0.1.0" in output
    assert "done" in output
    assert "Heads up" in output
