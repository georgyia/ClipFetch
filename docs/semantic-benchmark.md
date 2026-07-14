# Semantic indexing benchmark

Run the project-owned benchmark after installing the optional extra:

```bash
pip install -e ".[semantic]"
python scripts/benchmark_semantic.py
```

It creates fresh local catalogs containing 100, 1,000, and 10,000 short multilingual
captions, indexes them with the default quantized model, and prints wall time, throughput,
and process peak RSS. Model download/loading happens before timed indexing; the cache is
`~/.cache/clipfetch/fastembed`.

ONNX thread selection, CPU vector extensions, storage, thermals, and available memory
materially change results, so treat this snapshot as a baseline rather than a guarantee.
Measured July 15, 2026 on Apple Silicon (`arm64`), macOS 26.5.1, Python 3.13.4,
FastEmbed 0.8.0; the 10,000 row ran in a fresh process to keep the peak-RSS reading local:

```text
clips | wall_seconds | clips_per_second | peak_rss_mb
  100 |         0.47 |           213.95 |       697.6
 1000 |         4.53 |           220.65 |       697.6
10000 |        29.42 |           339.95 |       680.8
```

Pass explicit sizes to repeat one row in isolation, for example
`python scripts/benchmark_semantic.py 10000`.

Normal CI never runs this benchmark or downloads the model. The separately marked semantic
integration test uses the project-owned English/Spanish/Georgian evaluation corpus.
