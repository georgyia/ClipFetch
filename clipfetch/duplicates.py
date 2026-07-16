"""Report-only exact and bounded perceptual duplicate detection."""

from __future__ import annotations

import hashlib
import importlib
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from clipfetch.catalog import Catalog, CatalogError, CatalogRecord, MediaSignature
from clipfetch.errors import ClipFetchError

SIGNATURE_ALGORITHM = "gray-ahash-mean-8x8-8frames-v1"
SAMPLED_FRAME_COUNT = 8
MAX_DECODED_FRAMES_PER_SAMPLE = 120
MAX_DURATION_RELATIVE_DELTA = 0.15
MAX_DURATION_ABSOLUTE_DELTA = 1.0
MAX_NEAR_DISTANCE = 0.18


class DuplicateError(ClipFetchError):
    """Duplicate detection could not start or produce a safe report."""


class UnsupportedMedia(Exception):
    """The file has no decodable video stream or duration."""


class CorruptMedia(Exception):
    """The media container or sampled frames could not be decoded."""


@dataclass(frozen=True)
class MediaFingerprint:
    duration_seconds: float
    frame_hashes: tuple[int, ...]


class FingerprintBackend(Protocol):
    algorithm_version: str

    def fingerprint(self, path: Path) -> MediaFingerprint: ...


@dataclass(frozen=True)
class DuplicateMember:
    platform: str
    clip_id: str
    relative_path: str
    size: int


@dataclass(frozen=True)
class DuplicateGroup:
    match_type: str
    confidence: float
    distance: float
    recoverable_bytes: int
    members: tuple[DuplicateMember, ...]


@dataclass(frozen=True)
class SignatureOutcome:
    platform: str
    clip_id: str
    relative_path: str
    status: str
    error: str | None = None


@dataclass(frozen=True)
class DuplicateReport:
    scanned: int
    hashed: int
    hash_cache_hits: int
    decoded: int
    fingerprint_cache_hits: int
    groups: tuple[DuplicateGroup, ...]
    outcomes: tuple[SignatureOutcome, ...]


class PyAVFingerprintBackend:
    """Sample eight bounded frames through packaged PyAV; no FFmpeg binary."""

    algorithm_version = SIGNATURE_ALGORITHM

    def __init__(self) -> None:
        try:
            self._av = importlib.import_module("av")
        except ImportError as err:
            raise DuplicateError(
                'Near-duplicate support is not installed. Run: pip install '
                '"clipfetch[duplicates]" then retry with --include-near.'
            ) from err

    def fingerprint(self, path: Path) -> MediaFingerprint:
        try:
            with self._av.open(str(path)) as container:
                stream = next((item for item in container.streams if item.type == "video"), None)
                if stream is None:
                    raise UnsupportedMedia("no video stream")
                duration = _duration_seconds(container, stream, self._av)
                if duration is None or duration <= 0:
                    raise UnsupportedMedia("video duration is unavailable")
                hashes = []
                targets = [
                    duration * (index + 1) / (SAMPLED_FRAME_COUNT + 1)
                    for index in range(SAMPLED_FRAME_COUNT)
                ]
                for target in targets:
                    hashes.append(self._sample_hash(container, stream, target))
                return MediaFingerprint(duration, tuple(hashes))
        except (UnsupportedMedia, CorruptMedia):
            raise
        except Exception as err:
            raise CorruptMedia(str(err) or type(err).__name__) from err

    def _sample_hash(self, container: Any, stream: Any, target: float) -> int:
        try:
            time_base = float(stream.time_base)
            container.seek(max(0, int(target / time_base)), stream=stream, backward=True)
            selected = None
            for index, frame in enumerate(container.decode(stream)):
                selected = frame
                timestamp = float(frame.pts * stream.time_base) if frame.pts is not None else target
                if timestamp >= target or index + 1 >= MAX_DECODED_FRAMES_PER_SAMPLE:
                    break
            if selected is None:
                raise CorruptMedia("sampled frame could not be decoded")
            return _perceptual_hash(selected)
        except CorruptMedia:
            raise
        except Exception as err:
            raise CorruptMedia(str(err) or type(err).__name__) from err


def scan_duplicates(
    root: Path,
    *,
    include_near: bool = False,
    backend: FingerprintBackend | None = None,
    on_progress: Callable[[int, int, str, CatalogRecord], None] | None = None,
) -> DuplicateReport:
    """Cache signatures and return deterministic groups without touching media files."""
    if not root.is_dir():
        raise CatalogError(f"library directory does not exist: {root.resolve()}")
    if include_near and backend is None:
        backend = PyAVFingerprintBackend()
    algorithm = backend.algorithm_version if backend else SIGNATURE_ALGORITHM
    with Catalog.open(root) as catalog:
        records = catalog.all()
    hashed = hash_hits = decoded = fingerprint_hits = 0
    signatures: dict[tuple[str, str], MediaSignature] = {}
    outcomes: list[SignatureOutcome] = []
    total = len(records)
    for index, record in enumerate(records, start=1):
        path = root / record.relative_path
        try:
            stat = path.stat()
            if not path.is_file():
                raise FileNotFoundError(path)
        except OSError as err:
            status = "missing"
            outcomes.append(_outcome(record, status, str(err)))
            if on_progress:
                on_progress(index, total, status, record)
            continue
        with Catalog.open(root) as catalog:
            cached = catalog.get_media_signature(record.platform, record.clip_id)
        source_matches = bool(
            cached
            and cached.file_size == stat.st_size
            and cached.file_mtime_ns == stat.st_mtime_ns
        )
        if source_matches and cached is not None:
            file_hash = cached.file_hash
            hash_hits += 1
        else:
            try:
                file_hash = _file_hash(path)
                hashed += 1
            except OSError as err:
                status = "failed"
                outcomes.append(_outcome(record, status, str(err)))
                if on_progress:
                    on_progress(index, total, status, record)
                continue
        signature: MediaSignature
        if include_near and backend:
            reusable_fingerprint = (
                cached
                if (
                    source_matches
                    and cached is not None
                    and cached.file_hash == file_hash
                    and cached.algorithm_version == algorithm
                    and cached.status in {"complete", "unsupported", "corrupt"}
                )
                else None
            )
            if reusable_fingerprint is not None:
                signature = reusable_fingerprint
                fingerprint_hits += 1
            else:
                try:
                    fingerprint = backend.fingerprint(path)
                    decoded += 1
                    signature = _signature(
                        record,
                        file_hash,
                        stat.st_size,
                        stat.st_mtime_ns,
                        algorithm,
                        "complete",
                        fingerprint,
                    )
                except UnsupportedMedia as err:
                    decoded += 1
                    signature = _signature(
                        record,
                        file_hash,
                        stat.st_size,
                        stat.st_mtime_ns,
                        algorithm,
                        "unsupported",
                        error=str(err),
                    )
                except CorruptMedia as err:
                    decoded += 1
                    signature = _signature(
                        record,
                        file_hash,
                        stat.st_size,
                        stat.st_mtime_ns,
                        algorithm,
                        "corrupt",
                        error=str(err),
                    )
                except KeyboardInterrupt:
                    raise
                except Exception as err:
                    decoded += 1
                    signature = _signature(
                        record,
                        file_hash,
                        stat.st_size,
                        stat.st_mtime_ns,
                        algorithm,
                        "failed",
                        error=str(err),
                    )
                with Catalog.open(root) as catalog:
                    catalog.store_media_signature(signature)
        elif source_matches and cached:
            # A previous perceptual-decode failure is irrelevant to an exact-only
            # scan. Keep its cache for a later near retry, but report SHA success.
            signature = _signature(
                record,
                file_hash,
                stat.st_size,
                stat.st_mtime_ns,
                cached.algorithm_version,
                "exact-only",
            )
        else:
            signature = _signature(
                record,
                file_hash,
                stat.st_size,
                stat.st_mtime_ns,
                algorithm,
                "exact-only",
            )
            with Catalog.open(root) as catalog:
                catalog.store_media_signature(signature)
        signatures[(record.platform, record.clip_id)] = signature
        status = signature.status
        outcomes.append(_outcome(record, status, signature.error))
        if on_progress:
            on_progress(index, total, status, record)
    groups = _groups(records, signatures, include_near)
    return DuplicateReport(
        total,
        hashed,
        hash_hits,
        decoded,
        fingerprint_hits,
        groups,
        tuple(outcomes),
    )


def report_to_dict(report: DuplicateReport) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "scanned": report.scanned,
        "hashed": report.hashed,
        "hash_cache_hits": report.hash_cache_hits,
        "decoded": report.decoded,
        "fingerprint_cache_hits": report.fingerprint_cache_hits,
        "groups": [
            {
                "match_type": group.match_type,
                "confidence": group.confidence,
                "distance": group.distance,
                "recoverable_bytes": group.recoverable_bytes,
                "members": [asdict(member) for member in group.members],
            }
            for group in report.groups
        ],
        "outcomes": [asdict(outcome) for outcome in report.outcomes],
    }


def _signature(
    record: CatalogRecord,
    file_hash: str,
    file_size: int,
    file_mtime_ns: int,
    algorithm: str,
    status: str,
    fingerprint: MediaFingerprint | None = None,
    error: str | None = None,
) -> MediaSignature:
    return MediaSignature(
        record.platform,
        record.clip_id,
        file_hash,
        file_size,
        file_mtime_ns,
        algorithm,
        fingerprint.duration_seconds if fingerprint else None,
        fingerprint.frame_hashes if fingerprint else (),
        status,
        error,
        datetime.now(timezone.utc).isoformat(),
    )


def _outcome(record: CatalogRecord, status: str, error: str | None = None) -> SignatureOutcome:
    return SignatureOutcome(
        record.platform,
        record.clip_id,
        record.relative_path,
        status,
        error,
    )


def _groups(
    records: Sequence[CatalogRecord],
    signatures: dict[tuple[str, str], MediaSignature],
    include_near: bool,
) -> tuple[DuplicateGroup, ...]:
    record_by_key = {(record.platform, record.clip_id): record for record in records}
    by_hash: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for key, signature in signatures.items():
        by_hash[signature.file_hash].append(key)
    groups: list[DuplicateGroup] = []
    for keys in by_hash.values():
        if len(keys) > 1:
            groups.append(_group("exact", keys, record_by_key, signatures, 0.0))
    if include_near:
        representatives = [
            sorted(keys)[0]
            for _, keys in sorted(by_hash.items())
            if signatures[sorted(keys)[0]].status == "complete"
        ]
        edges: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
        distances: dict[frozenset[tuple[str, str]], float] = {}
        for left_index, left in enumerate(representatives):
            for right in representatives[left_index + 1 :]:
                distance = _near_distance(signatures[left], signatures[right])
                if distance is not None and distance <= MAX_NEAR_DISTANCE:
                    edges[left].add(right)
                    edges[right].add(left)
                    distances[frozenset((left, right))] = distance
        seen: set[tuple[str, str]] = set()
        for start in sorted(edges):
            if start in seen:
                continue
            stack = [start]
            component = set()
            while stack:
                key = stack.pop()
                if key in component:
                    continue
                component.add(key)
                stack.extend(edges[key])
            seen.update(component)
            if len(component) > 1:
                component_edges = [
                    value
                    for pair, value in distances.items()
                    if pair.issubset(component)
                ]
                groups.append(
                    _group(
                        "probable",
                        sorted(component),
                        record_by_key,
                        signatures,
                        max(component_edges),
                    )
                )
    groups.sort(
        key=lambda group: (
            0 if group.match_type == "exact" else 1,
            tuple((member.platform, member.clip_id) for member in group.members),
        )
    )
    return tuple(groups)


def _group(
    match_type: str,
    keys: Sequence[tuple[str, str]],
    records: dict[tuple[str, str], CatalogRecord],
    signatures: dict[tuple[str, str], MediaSignature],
    distance: float,
) -> DuplicateGroup:
    members = tuple(
        DuplicateMember(
            records[key].platform,
            records[key].clip_id,
            records[key].relative_path,
            signatures[key].file_size,
        )
        for key in sorted(keys)
    )
    recoverable = sum(member.size for member in members) - max(member.size for member in members)
    return DuplicateGroup(
        match_type,
        round(1.0 - distance, 6),
        round(distance, 6),
        recoverable,
        members,
    )


def _near_distance(left: MediaSignature, right: MediaSignature) -> float | None:
    if (
        left.duration_seconds is None
        or right.duration_seconds is None
        or not left.frame_hashes
        or not right.frame_hashes
    ):
        return None
    duration_delta = abs(left.duration_seconds - right.duration_seconds)
    relative_delta = duration_delta / max(left.duration_seconds, right.duration_seconds)
    if (
        duration_delta > MAX_DURATION_ABSOLUTE_DELTA
        and relative_delta > MAX_DURATION_RELATIVE_DELTA
    ):
        return None
    visual = min(
        _aligned_distance(left.frame_hashes, right.frame_hashes, offset)
        for offset in (-1, 0, 1)
    )
    duration_penalty = min(relative_delta / MAX_DURATION_RELATIVE_DELTA, 1.0) * 0.05
    return min(1.0, visual + duration_penalty)


def _aligned_distance(left: tuple[int, ...], right: tuple[int, ...], offset: int) -> float:
    if offset < 0:
        pairs = zip(left[-offset:], right)
    elif offset > 0:
        pairs = zip(left, right[offset:])
    else:
        pairs = zip(left, right)
    values = [_frame_distance(one, two) for one, two in pairs]
    return sum(values) / len(values) if values else 1.0


def _frame_distance(left: int, right: int) -> float:
    pattern_mask = (1 << 56) - 1
    pattern = bin((left ^ right) & pattern_mask).count("1") / 56
    mean = abs((left >> 56) - (right >> 56)) / 255
    return pattern * 0.85 + mean * 0.15


def _perceptual_hash(frame: Any) -> int:
    scaled = frame.reformat(width=8, height=8, format="gray")
    plane = scaled.planes[0]
    raw = bytes(plane)
    pixels = [
        raw[row * plane.line_size + column]
        for row in range(8)
        for column in range(8)
    ]
    mean = round(sum(pixels) / len(pixels))
    pattern = 0
    for pixel in pixels[:56]:
        pattern = (pattern << 1) | int(pixel >= mean)
    return (mean << 56) | pattern


def _duration_seconds(container: Any, stream: Any, av_module: Any) -> float | None:
    if stream.duration is not None and stream.time_base is not None:
        return float(stream.duration * stream.time_base)
    if container.duration is not None:
        return float(container.duration / av_module.time_base)
    return None


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
