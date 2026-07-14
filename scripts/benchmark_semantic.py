"""Reproducible CPU benchmark for issue #22 (not part of normal CI)."""

from __future__ import annotations

import argparse
import resource
import sys
import tempfile
import time
from pathlib import Path

from clipfetch.catalog import Catalog, CatalogRecord
from clipfetch.semantic import FastEmbedder, semantic_index

COUNTS = (100, 1_000, 10_000)
CAPTIONS = (
    "How to build a startup from zero #entrepreneurship",
    "Consejos para crear una empresa #emprendimiento",
    "როგორ შევქმნათ ახალი კომპანია #ბიზნესი",
)


def _peak_rss_mb() -> float:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    divisor = 1024 * 1024 if sys.platform == "darwin" else 1024
    return rss / divisor


def _prepare(root: Path, count: int) -> None:
    with Catalog.open(root) as catalog:
        for index in range(count):
            ident = f"BENCH{index}"
            path = root / f"reel_{index:05d}_{ident}.mp4"
            path.touch()
            catalog.upsert(
                CatalogRecord(
                    platform="instagram",
                    clip_id=ident,
                    relative_path=path.name,
                    file_size=0,
                    file_mtime_ns=path.stat().st_mtime_ns,
                    downloaded_at="2026-01-01T00:00:00+00:00",
                    source_url=None,
                    author="benchmark",
                    caption=CAPTIONS[index % len(CAPTIONS)],
                    likes=None,
                    metadata_state="benchmark",
                )
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("counts", nargs="*", type=int, default=list(COUNTS))
    args = parser.parse_args()
    embedder = FastEmbedder()  # model load/download is deliberately outside timings
    print("clips | wall_seconds | clips_per_second | peak_rss_mb")
    for count in args.counts:
        with tempfile.TemporaryDirectory(prefix="clipfetch-benchmark-") as directory:
            root = Path(directory)
            _prepare(root, count)
            started = time.perf_counter()
            report = semantic_index(root, embedder)
            elapsed = time.perf_counter() - started
            print(
                f"{report.indexed:5d} | {elapsed:12.2f} | "
                f"{report.indexed / elapsed:16.2f} | {_peak_rss_mb():11.1f}"
            )


if __name__ == "__main__":
    main()
