from __future__ import annotations

import json
from pathlib import Path

import pytest

from clipfetch.visible_text import CorruptMedia, RapidOCRExtractor

pytestmark = [pytest.mark.integration, pytest.mark.ocr_integration]
FIXTURES = Path(__file__).parents[1] / "fixtures/visible_text"


def test_real_model_meets_fixture_precision_and_recall_floor():
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    extractor = RapidOCRExtractor()
    true_positive = false_positive = false_negative = 0
    for fixture in manifest["fixtures"]:
        try:
            result = extractor.extract(FIXTURES / fixture["file"])
            actual = {" ".join(item.text.casefold().split()) for item in result.segments}
            status = "complete"
        except CorruptMedia:
            actual = set()
            status = "corrupt"
        expected = {" ".join(item.casefold().split()) for item in fixture["expected"]}
        true_positive += len(actual & expected)
        false_positive += len(actual - expected)
        false_negative += len(expected - actual)
        assert status == fixture.get("expected_status", "complete")
    precision = true_positive / (true_positive + false_positive or 1)
    recall = true_positive / (true_positive + false_negative or 1)
    assert precision >= 0.95
    assert recall >= 0.70
