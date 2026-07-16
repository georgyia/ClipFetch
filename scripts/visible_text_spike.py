"""Isolated bounded OCR spike used by the reproducible benchmark only.

This module intentionally is not imported by ClipFetch and does not expose a
user command. The evaluated backend did not pass the promotion threshold.
"""

from __future__ import annotations

import difflib
import importlib
import math
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SAMPLE_INTERVAL_SECONDS = 2.0
MAX_SAMPLED_FRAMES = 30
MAX_DECODED_FRAMES_PER_SAMPLE = 120
MIN_CONFIDENCE = 0.85
DEDUPLICATION_SIMILARITY = 0.88
MAX_RETAINED_CHARACTERS = 512
SAMPLE_POLICY = "one-per-2s,max-30,decode-max-120-per-sample,v1"


class UnsupportedMedia(Exception):
    pass


class CorruptMedia(Exception):
    pass


@dataclass(frozen=True)
class SampledFrame:
    timestamp_seconds: float
    image: Any


@dataclass(frozen=True)
class Segment:
    timestamp_seconds: float
    text: str
    confidence: float


@dataclass(frozen=True)
class Result:
    text: str
    segments: tuple[Segment, ...]
    confidence: float | None


def sample_timestamps(duration_seconds: float) -> tuple[float, ...]:
    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise UnsupportedMedia("video duration is unavailable")
    count = min(MAX_SAMPLED_FRAMES, max(1, math.ceil(duration_seconds / 2.0)))
    return tuple(index * SAMPLE_INTERVAL_SECONDS for index in range(count))


def retain_lines(lines: list[Segment]) -> Result:
    retained: list[Segment] = []
    for line in lines:
        text = " ".join(unicodedata.normalize("NFKC", line.text).split())
        if not text or not math.isfinite(line.confidence) or line.confidence < MIN_CONFIDENCE:
            continue
        candidate = Segment(line.timestamp_seconds, text, line.confidence)
        duplicate_at = next(
            (
                index
                for index, existing in enumerate(retained)
                if _similarity(existing.text, candidate.text) >= DEDUPLICATION_SIMILARITY
            ),
            None,
        )
        if duplicate_at is None:
            retained.append(candidate)
        elif candidate.confidence > retained[duplicate_at].confidence:
            retained[duplicate_at] = candidate

    capped: list[Segment] = []
    used = 0
    for item in sorted(retained, key=lambda segment: segment.timestamp_seconds):
        separator = int(bool(capped))
        remaining = MAX_RETAINED_CHARACTERS - used - separator
        if remaining <= 0:
            break
        text = item.text[:remaining].rstrip()
        if not text:
            break
        capped.append(Segment(item.timestamp_seconds, text, item.confidence))
        used += separator + len(text)
    combined = "\n".join(item.text for item in capped)
    confidence = sum(item.confidence for item in capped) / len(capped) if capped else None
    return Result(combined, tuple(capped), confidence)


class RapidOCRSpike:
    model_id = "rapidocr/pp-ocrv6-small"
    revision = "rapidocr-3.9.1/onnxruntime-cpu"

    def __init__(self) -> None:
        self._av = importlib.import_module("av")
        RapidOCR = importlib.import_module("rapidocr").RapidOCR
        self._engine = RapidOCR()

    def extract(self, path: Path) -> Result:
        lines: list[Segment] = []
        try:
            with self._av.open(str(path)) as container:
                stream = next((item for item in container.streams if item.type == "video"), None)
                if stream is None:
                    raise UnsupportedMedia("no video stream")
                duration = _duration_seconds(container, stream, self._av)
                if duration is None or duration <= 0:
                    raise UnsupportedMedia("video duration is unavailable")
                for target in sample_timestamps(duration):
                    frame = self._sample_frame(container, stream, target)
                    output = self._engine(frame.image)
                    lines.extend(
                        Segment(frame.timestamp_seconds, str(text), float(score))
                        for text, score in zip(output.txts or (), output.scores or ())
                    )
        except UnsupportedMedia:
            raise
        except Exception as error:
            raise CorruptMedia(str(error) or type(error).__name__) from error
        return retain_lines(lines)

    def _sample_frame(self, container: Any, stream: Any, target: float) -> SampledFrame:
        time_base = float(stream.time_base)
        container.seek(max(0, int(target / time_base)), stream=stream, backward=True)
        selected = None
        timestamp = target
        for index, frame in enumerate(container.decode(stream)):
            selected = frame
            if frame.pts is not None:
                timestamp = max(0.0, float(frame.pts * stream.time_base))
            if timestamp >= target or index + 1 >= MAX_DECODED_FRAMES_PER_SAMPLE:
                break
        if selected is None:
            raise CorruptMedia("sampled frame could not be decoded")
        return SampledFrame(timestamp, selected.to_ndarray(format="bgr24"))


def _duration_seconds(container: Any, stream: Any, av_module: Any) -> float | None:
    if stream.duration is not None and stream.time_base is not None:
        return float(stream.duration * stream.time_base)
    if container.duration is not None:
        return float(container.duration / av_module.time_base)
    return None


def _similarity(left: str, right: str) -> float:
    return difflib.SequenceMatcher(None, left.casefold(), right.casefold()).ratio()
