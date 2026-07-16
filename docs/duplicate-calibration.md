# Near-duplicate calibration

ClipFetch's probable-duplicate detector samples eight evenly spaced frames and decodes at
most 120 frames while seeking each sample. Every frame is reduced to a 56-bit grayscale
average-hash pattern plus its 8-bit mean luminance. Candidate clips must have compatible
durations and a combined visual/duration distance of at most `0.18`.

The opt-in `tests/integration/test_duplicate_fingerprints.py` test generates its corpus from
FFmpeg's deterministic `testsrc2` and `smptebars` sources. No downloaded or third-party
media is used. Results measured on macOS arm64 with PyAV 18 and FFmpeg 8 are:

| Base versus | Distance | Expected |
|---|---:|---|
| Matroska remux | 0.0000 | probable duplicate |
| MPEG-4 recompression | 0.0021 | probable duplicate |
| 50% resize | 0.0000 | probable duplicate |
| 0.2s head / 0.2s tail trim | 0.0500 | probable duplicate |
| Opaque title-bar overlay | 0.1230 | probable duplicate |
| Unrelated SMPTE bars, same duration | 0.4673 | not grouped |

At the selected threshold this bounded corpus has 0/5 false negatives and 0/1 false
positives. That is calibration evidence, not a universal accuracy claim: animation, nearly
static slides, large overlays, mirrored/cropped footage, or edits between sampled frames can
still fool a perceptual hash. Results are deliberately labeled **probable** and require human
review. Exact SHA-256 groups have no hash-collision false positives for practical cleanup.

Run the calibration explicitly with:

```bash
pytest -q -m duplicate_integration tests/integration/test_duplicate_fingerprints.py
```
