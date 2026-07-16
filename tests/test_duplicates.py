from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from clipfetch.catalog import Catalog, CatalogRecord
from clipfetch.cli import main
from clipfetch.duplicates import (
    CorruptMedia,
    DuplicateError,
    MediaFingerprint,
    PyAVFingerprintBackend,
    UnsupportedMedia,
    report_to_dict,
    scan_duplicates,
)


def _record(
    ident: str,
    body: bytes,
    *,
    platform: str = "instagram",
    caption: str | None = None,
) -> CatalogRecord:
    noun = "reel" if platform == "instagram" else "tiktok"
    return CatalogRecord(
        platform=platform,
        clip_id=ident,
        relative_path=f"{noun}_001_{ident}.mp4",
        file_size=len(body),
        file_mtime_ns=1,
        downloaded_at="2026-01-01T00:00:00+00:00",
        source_url=None,
        author="author",
        caption=caption,
        likes=1,
        metadata_state="catalog",
    )


def _library(root: Path, *items: tuple[CatalogRecord, bytes]) -> None:
    with Catalog.open(root) as catalog:
        for record, body in items:
            catalog.upsert(record)
            (root / record.relative_path).write_bytes(body)


def _hash(mean: int, pattern: int) -> int:
    return (mean << 56) | (pattern & ((1 << 56) - 1))


class FakeBackend:
    algorithm_version = "fake-v1"

    def __init__(self, interrupt_at: int | None = None) -> None:
        self.calls: list[str] = []
        self.interrupt_at = interrupt_at

    def fingerprint(self, path: Path) -> MediaFingerprint:
        self.calls.append(path.name)
        if len(self.calls) == self.interrupt_at:
            raise KeyboardInterrupt
        if "UNSUPPORTED" in path.name:
            raise UnsupportedMedia("no video stream")
        if "CORRUPT" in path.name:
            raise CorruptMedia("invalid media")
        if "FAIL" in path.name:
            raise RuntimeError("backend failed")
        if "UNRELATED" in path.name:
            return MediaFingerprint(10.0, tuple(_hash(120, 0) for _ in range(8)))
        if "LONG" in path.name:
            return MediaFingerprint(20.0, tuple(_hash(100, (1 << 56) - 1) for _ in range(8)))
        pattern = (1 << 56) - 1
        hashes = [_hash(100, pattern) for _ in range(8)]
        if "NEAR2" in path.name:
            hashes[3] ^= 0b111
            return MediaFingerprint(10.2, tuple(hashes))
        return MediaFingerprint(10.0, tuple(hashes))


def test_exact_duplicates_are_deterministic_and_media_is_unchanged(tmp_path):
    same = b"identical complete media bytes"
    a = _record("A", same)
    b = _record("B", same, platform="tiktok")
    c = _record("C", b"different")
    _library(tmp_path, (a, same), (b, same), (c, b"different"))
    before = {
        record.relative_path: (
            (tmp_path / record.relative_path).read_bytes(),
            (tmp_path / record.relative_path).stat().st_mtime_ns,
        )
        for record in (a, b, c)
    }

    first = scan_duplicates(tmp_path)
    assert first.hashed == 3 and first.hash_cache_hits == 0
    assert len(first.groups) == 1
    group = first.groups[0]
    assert group.match_type == "exact" and group.confidence == 1.0
    assert [(item.platform, item.clip_id) for item in group.members] == [
        ("instagram", "A"),
        ("tiktok", "B"),
    ]
    assert group.recoverable_bytes == len(same)
    second = scan_duplicates(tmp_path)
    third = scan_duplicates(tmp_path)
    assert second.hash_cache_hits == third.hash_cache_hits == 3
    assert report_to_dict(second) == report_to_dict(third)
    for record in (a, b, c):
        path = tmp_path / record.relative_path
        assert (path.read_bytes(), path.stat().st_mtime_ns) == before[record.relative_path]


def test_changed_file_invalidates_exact_signature_even_for_same_clip_id(tmp_path):
    body = b"same"
    a = _record("A", body)
    b = _record("B", body)
    _library(tmp_path, (a, body), (b, body))
    assert len(scan_duplicates(tmp_path).groups) == 1
    (tmp_path / a.relative_path).write_bytes(b"changed-and-longer")
    report = scan_duplicates(tmp_path)
    assert report.hashed == 1 and report.hash_cache_hits == 1
    assert report.groups == ()


def test_probable_near_groups_use_media_not_similar_metadata(tmp_path):
    records = [
        _record("NEAR1", b"one", caption="same topic"),
        _record("NEAR2", b"two", caption="same topic"),
        _record("UNRELATED", b"three", caption="same topic"),
        _record("LONG", b"four", caption="same topic"),
    ]
    _library(tmp_path, *((record, record.clip_id.encode()) for record in records))
    report = scan_duplicates(tmp_path, include_near=True, backend=FakeBackend())
    probable = [group for group in report.groups if group.match_type == "probable"]
    assert len(probable) == 1
    assert [item.clip_id for item in probable[0].members] == ["NEAR1", "NEAR2"]
    assert probable[0].confidence > 0.9


def test_fingerprint_cache_file_and_algorithm_invalidation(tmp_path):
    records = [_record("NEAR1", b"one"), _record("NEAR2", b"two")]
    _library(tmp_path, *((record, record.clip_id.encode()) for record in records))
    first_backend = FakeBackend()
    first = scan_duplicates(tmp_path, include_near=True, backend=first_backend)
    assert first.hashed == 2 and first.decoded == 2
    cached_backend = FakeBackend()
    cached = scan_duplicates(tmp_path, include_near=True, backend=cached_backend)
    assert cached.hash_cache_hits == 2 and cached.fingerprint_cache_hits == 2
    assert cached_backend.calls == []

    changed_backend = FakeBackend()
    changed_backend.algorithm_version = "fake-v2"
    changed = scan_duplicates(tmp_path, include_near=True, backend=changed_backend)
    assert changed.hash_cache_hits == 2 and changed.decoded == 2
    assert len(changed_backend.calls) == 2


def test_missing_unsupported_corrupt_failed_and_interruption_resume(tmp_path):
    records = [
        _record("A", b"a"),
        _record("B", b"b"),
        _record("UNSUPPORTED", b"u"),
        _record("CORRUPT", b"c"),
        _record("FAIL", b"f"),
        _record("MISSING", b"m"),
    ]
    _library(tmp_path, *((record, record.clip_id.encode()) for record in records))
    (tmp_path / records[-1].relative_path).unlink()
    report = scan_duplicates(tmp_path, include_near=True, backend=FakeBackend())
    statuses = {outcome.clip_id: outcome.status for outcome in report.outcomes}
    assert statuses == {
        "A": "complete",
        "B": "complete",
        "CORRUPT": "corrupt",
        "FAIL": "failed",
        "MISSING": "missing",
        "UNSUPPORTED": "unsupported",
    }
    exact_statuses = {
        outcome.clip_id: outcome.status for outcome in scan_duplicates(tmp_path).outcomes
    }
    assert exact_statuses["CORRUPT"] == "exact-only"
    assert exact_statuses["UNSUPPORTED"] == "exact-only"
    assert exact_statuses["MISSING"] == "missing"

    fresh = tmp_path / "fresh"
    fresh.mkdir()
    _library(fresh, *((record, record.clip_id.encode()) for record in records[:2]))
    with pytest.raises(KeyboardInterrupt):
        scan_duplicates(fresh, include_near=True, backend=FakeBackend(interrupt_at=2))
    resumed_backend = FakeBackend()
    resumed = scan_duplicates(fresh, include_near=True, backend=resumed_backend)
    assert resumed.fingerprint_cache_hits == 1 and resumed.decoded == 1


def test_duplicates_cli_json_is_unstyled_and_report_only(tmp_path, capsys):
    body = b"duplicate"
    _library(tmp_path, (_record("A", body), body), (_record("B", body), body))
    capsys.readouterr()
    assert main(["library", "duplicates", str(tmp_path), "--json"]) == 0
    output = capsys.readouterr().out
    assert "ClipFetch" not in output and "\x1b[" not in output
    value = json.loads(output)
    assert value["schema_version"] == 1
    assert value["groups"][0]["match_type"] == "exact"
    assert [member["clip_id"] for member in value["groups"][0]["members"]] == ["A", "B"]


def test_base_exact_scan_does_not_require_optional_decoder(tmp_path, monkeypatch):
    body = b"duplicate"
    _library(tmp_path, (_record("A", body), body), (_record("B", body), body))
    monkeypatch.setitem(sys.modules, "av", None)
    assert len(scan_duplicates(tmp_path).groups) == 1
    with pytest.raises(DuplicateError, match=r'clipfetch\[duplicates\]'):
        PyAVFingerprintBackend()
