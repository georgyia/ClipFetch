"""Opt-in multilingual quality smoke test; downloads the real model."""

from pathlib import Path

import pytest

from clipfetch.catalog import Catalog, CatalogRecord
from clipfetch.semantic import FastEmbedder, semantic_index, semantic_search

pytestmark = [pytest.mark.integration, pytest.mark.semantic_integration]
pytest.importorskip("fastembed")


def test_real_model_connects_english_spanish_and_georgian(tmp_path: Path):
    records = [
        ("EN", "How to build a startup from zero"),
        ("ES", "Consejos para crear una empresa"),
        ("KA", "როგორ შევქმნათ ახალი კომპანია"),
        ("FOOD", "A recipe for tomato pasta"),
    ]
    with Catalog.open(tmp_path) as catalog:
        for ident, caption in records:
            path = tmp_path / f"reel_001_{ident}.mp4"
            path.write_bytes(b"video")
            catalog.upsert(
                CatalogRecord(
                    platform="instagram",
                    clip_id=ident,
                    relative_path=path.name,
                    file_size=5,
                    file_mtime_ns=path.stat().st_mtime_ns,
                    downloaded_at="2026-01-01T00:00:00+00:00",
                    source_url=None,
                    author=None,
                    caption=caption,
                    likes=None,
                    metadata_state="sidecar-v2",
                )
            )
    embedder = FastEmbedder()
    semantic_index(tmp_path, embedder)
    result = semantic_search(tmp_path, "entrepreneurship advice", embedder)
    top_three = {match.record.clip_id for match in result.matches[:3]}
    assert top_three == {"EN", "ES", "KA"}
