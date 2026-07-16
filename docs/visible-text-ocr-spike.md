# Visible-text OCR spike (not promoted)

Issue #28 evaluated a local ONNX OCR path for text that appears in video frames but not
in captions or speech. The spike is reproducible, but it was **not promoted to a ClipFetch
command**: the selected backend missed the complete mixed-script fixture on every tested
runtime and exceeded the resource gate on at least one operating system.

## Candidate and compatibility

The candidate is RapidOCR 3.9.1 with its packaged PP-OCRv6 small detection and recognition
models, using ONNX Runtime on CPU. RapidOCR declares Python 3.8+ support and packages its
three default models; its installation guide reports a roughly 27 MB wheel plus OpenCV,
NumPy, Shapely, and other dependencies. ONNX Runtime's current CPU package supports macOS
and Arm, while 1.19.2 provides the required CPython 3.9 macOS and Linux wheels.

- [RapidOCR installation and dependency list](https://rapidai.github.io/RapidOCRDocs/main/install_usage/rapidocr/install/)
- [RapidOCR model/language matrix](https://rapidai.github.io/RapidOCRDocs/latest/model_list/)
- [ONNX Runtime CPU installation](https://onnxruntime.ai/docs/get-started/with-python.html)
- [ONNX Runtime 1.19.2 Python 3.9 wheels](https://pypi.org/project/onnxruntime/1.19.2/)

| Host | Python / runtime | Result |
|---|---|---|
| macOS 26.5, Apple Silicon | Python 3.9.6, ONNX Runtime 1.19.2 | Installed and completed corpus |
| macOS 26.5, Apple Silicon | Python 3.13.4, ONNX Runtime 1.27.0 | Installed and completed corpus |
| Ubuntu GitHub runner, x86-64 | Python 3.13.14, ONNX Runtime 1.27.0 | Installed and completed corpus |

Python 3.9 must remain on ONNX Runtime 1.19.2 because the 1.20 line dropped Python 3.9.
The candidate stayed isolated from ClipFetch's base imports throughout the spike.

## Corpus and policy

The project-owned corpus is in `tests/fixtures/visible_text/`; `manifest.json` records
ground truth and `scripts/generate_visible_text_fixtures.py` records how the tiny MP4s were
built. It covers a static title, moving subtitles, a repeated caption, low contrast, no
text, 25-degree rotation, mixed Latin/Japanese/Arabic Unicode, and a corrupt video.

The evaluated sampling policy was one frame every two seconds, at most 30 sampled frames.
Each seek decoded at most 120 frames, so even a malformed keyframe index could not create
an unbounded decode path. Unit tests preserve both caps.

The corpus/pilot sweep selected these post-processing values:

- minimum confidence **0.85**: correct retained corpus lines scored at least 0.97; the
  materially incomplete mixed-script line scored 0.817;
- edit-similarity deduplication **0.88**: it merged the repeated/punctuation variant while
  keeping the two changing subtitle lines separate;
- maximum retained text **512 characters per clip**: more than ten times the corpus's
  largest two-frame retained result, but still a hard semantic-input bound.

Promotion required at least 0.95 exact-line precision and 0.70 recall, with corrupt/no-text
fixtures producing no retained text. The resource gate was 350 MB of logical installed OCR
files and 600 MB peak RSS, chosen to keep the optional feature near the existing semantic
extra rather than adding an effectively second application runtime.

## Results

All three runs produced the same quality result: six exact retained lines, no false
positives, and three false negatives. Static, moving, repeated, low-contrast, rotated, and
no-text behavior passed. The backend returned no accepted text for `Café • 東京 • مرحبا`;
the default recognition model is not a reliable single-pass mixed-script solution.

| Host | Precision | Recall | Wall time | Peak RSS | Logical dependency files | Packaged models |
|---|---:|---:|---:|---:|---:|---:|
| macOS / Python 3.9 | 1.000 | 0.667 | 44.40 s | 510.6 MB | 313.5 MB | 31.7 MB |
| macOS / Python 3.13 | 1.000 | 0.667 | 22.42 s | 631.4 MB | 333.1 MB | 31.7 MB |
| Linux / Python 3.13 | 1.000 | 0.667 | 5.86 s | 558.8 MB | 497.5 MB | 31.7 MB |

The models are packaged in the RapidOCR wheel, so external model-cache size was zero.
macOS also warned that PyAV and OpenCV load separate bundled FFmpeg libraries, another
reason not to add this stack until the integration story improves.

## Reproduce

From a clean checkout, create an isolated environment and install:

```text
pip install rapidocr==3.9.1 "av>=11"
pip install onnxruntime==1.19.2  # Python 3.9
# or: pip install onnxruntime>=1.20  # Python 3.10+
PYTHONPATH=. python scripts/benchmark_visible_text.py
```

The script emits the fixture-level outputs, precision/recall, CPU wall time, peak RSS,
logical installed dependency bytes, packaged model bytes, and external cache bytes as
JSON. Normal CI does not install the OCR stack or run the real model.

## Recommendation

Keep using captions, transcripts, retained comments, and manual topics as ClipFetch's
semantic inputs. Revisit visible-text extraction when a single local multilingual ONNX
recognizer can pass the mixed-script corpus without language-specific multi-pass models,
or when an explicit user-selected language mode can meet the same quality/resource gates.
Until then, shipping the proposed command would silently omit exactly the Unicode text the
multilingual semantic workflow is intended to preserve.
