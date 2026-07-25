from __future__ import annotations

from clipfetch.api import capabilities


def test_thumbnails_capability_reflects_ffmpeg(monkeypatch):
    monkeypatch.setattr(capabilities.shutil, "which", lambda name: "/usr/bin/ffmpeg")
    matrix = capabilities.capability_matrix()
    assert matrix["thumbnails"]["available"] is True
    assert "reason" not in matrix["thumbnails"]


def test_thumbnails_capability_off_without_ffmpeg(monkeypatch):
    monkeypatch.setattr(capabilities.shutil, "which", lambda name: None)
    matrix = capabilities.capability_matrix()
    assert matrix["thumbnails"] == {"available": False, "reason": "ffmpeg_missing"}
