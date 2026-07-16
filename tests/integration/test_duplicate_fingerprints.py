"""Opt-in calibration against deterministic project-generated video variants."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from clipfetch.catalog import Catalog, CatalogRecord
from clipfetch.duplicates import MAX_NEAR_DISTANCE, PyAVFingerprintBackend, scan_duplicates

pytestmark = [pytest.mark.integration, pytest.mark.duplicate_integration]
pytest.importorskip("av")


def _ffmpeg(*arguments: str) -> None:
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *arguments],
        check=True,
    )


def test_transformed_fixture_calibration(tmp_path: Path):
    if shutil.which("ffmpeg") is None:
        pytest.skip("fixture generation requires ffmpeg")
    base = tmp_path / "base.mp4"
    _ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=320x240:rate=12:duration=4",
        "-c:v",
        "mpeg4",
        "-q:v",
        "3",
        "-an",
        str(base),
    )
    commands = {
        "remux": ("-i", str(base), "-c", "copy", str(tmp_path / "remux.mkv")),
        "recompressed": (
            "-i",
            str(base),
            "-c:v",
            "mpeg4",
            "-q:v",
            "12",
            "-an",
            str(tmp_path / "recompressed.mp4"),
        ),
        "resized": (
            "-i",
            str(base),
            "-vf",
            "scale=160:120",
            "-c:v",
            "mpeg4",
            "-q:v",
            "5",
            "-an",
            str(tmp_path / "resized.mp4"),
        ),
        "trimmed": (
            "-ss",
            "0.2",
            "-i",
            str(base),
            "-t",
            "3.6",
            "-c:v",
            "mpeg4",
            "-q:v",
            "5",
            "-an",
            str(tmp_path / "trimmed.mp4"),
        ),
        "overlay": (
            "-i",
            str(base),
            "-vf",
            "drawbox=x=10:y=10:w=250:h=35:color=black@0.8:t=fill",
            "-c:v",
            "mpeg4",
            "-q:v",
            "5",
            "-an",
            str(tmp_path / "overlay.mp4"),
        ),
        "unrelated": (
            "-f",
            "lavfi",
            "-i",
            "smptebars=size=320x240:rate=12:duration=4",
            "-c:v",
            "mpeg4",
            "-q:v",
            "3",
            "-an",
            str(tmp_path / "unrelated.mp4"),
        ),
    }
    for arguments in commands.values():
        _ffmpeg(*arguments)

    paths = [base, *(Path(arguments[-1]) for arguments in commands.values())]
    with Catalog.open(tmp_path) as catalog:
        for path in paths:
            stat = path.stat()
            catalog.upsert(
                CatalogRecord(
                    "fixture",
                    path.stem,
                    path.name,
                    stat.st_size,
                    stat.st_mtime_ns,
                    "2026-01-01T00:00:00+00:00",
                    None,
                    None,
                    None,
                    None,
                    "fixture",
                )
            )
    report = scan_duplicates(
        tmp_path,
        include_near=True,
        backend=PyAVFingerprintBackend(),
    )
    probable = [group for group in report.groups if group.match_type == "probable"]
    assert len(probable) == 1
    assert {member.clip_id for member in probable[0].members} == {
        "base",
        "overlay",
        "recompressed",
        "remux",
        "resized",
        "trimmed",
    }
    assert probable[0].distance <= MAX_NEAR_DISTANCE
    assert all(member.clip_id != "unrelated" for member in probable[0].members)
