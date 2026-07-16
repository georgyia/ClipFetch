"""Run the explicit real-model visible-text fixture benchmark and emit JSON."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import resource
import sys
import time
from pathlib import Path
from typing import Any

from scripts.visible_text_spike import SAMPLE_POLICY, CorruptMedia, RapidOCRSpike

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/visible_text"


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def _tokens(values: list[str]) -> set[str]:
    return {_normalized(item) for item in values if _normalized(item)}


def _distribution_bytes(name: str) -> int:
    distribution = importlib.metadata.distribution(name)
    total = 0
    for file in distribution.files or ():
        path = Path(distribution.locate_file(file))
        try:
            total += path.stat().st_size
        except OSError:
            pass
    return total


def main() -> None:
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    started = time.monotonic()
    extractor = RapidOCRSpike()
    fixture_results: list[dict[str, Any]] = []
    true_positive = false_positive = false_negative = 0
    for fixture in manifest["fixtures"]:
        path = FIXTURES / fixture["file"]
        item_started = time.monotonic()
        status = "complete"
        try:
            result = extractor.extract(path)
            actual = [segment.text for segment in result.segments]
        except CorruptMedia:
            status = "corrupt"
            actual = []
        expected = fixture["expected"]
        actual_tokens = _tokens(actual)
        expected_tokens = _tokens(expected)
        true_positive += len(actual_tokens & expected_tokens)
        false_positive += len(actual_tokens - expected_tokens)
        false_negative += len(expected_tokens - actual_tokens)
        fixture_results.append(
            {
                "file": fixture["file"],
                "category": fixture["category"],
                "status": status,
                "expected": expected,
                "actual": actual,
                "processing_seconds": round(time.monotonic() - item_started, 4),
            }
        )
    precision = true_positive / (true_positive + false_positive or 1)
    recall = true_positive / (true_positive + false_negative or 1)
    max_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() != "Darwin":
        max_rss *= 1024
    packages = (
        "rapidocr",
        "onnxruntime",
        "opencv-python",
        "av",
        "numpy",
        "shapely",
        "pyclipper",
        "pillow",
    )
    dependency_bytes = sum(_distribution_bytes(name) for name in packages)
    model_root = Path(
        importlib.metadata.distribution("rapidocr").locate_file("rapidocr/models")
    )
    model_bytes = sum(
        path.stat().st_size
        for path in model_root.glob("**/*")
        if path.is_file()
    )
    report = {
        "schema_version": 1,
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "model_id": extractor.model_id,
        "model_revision": extractor.revision,
        "sample_policy": SAMPLE_POLICY,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "wall_seconds": round(time.monotonic() - started, 4),
        "peak_rss_bytes": max_rss,
        "dependency_bytes": dependency_bytes,
        "packaged_model_bytes": model_bytes,
        "external_model_cache_bytes": 0,
        "fixtures": fixture_results,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
