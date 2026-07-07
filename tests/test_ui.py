import io

from clipfetch.ui import Console, human_size, render_bar


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
