# ClipFetch documentation

Deep-dive documentation for ClipFetch and the planned ClipFetch Watch streaming interface. Start with the
[project README](../README.md) for installation and everyday usage.

## Product & roadmap

- **[ROADMAP.md](ROADMAP.md)** — the short version: delivery phases and release scope for ClipFetch Watch.
- **[clipfetch-watch-plan.md](clipfetch-watch-plan.md)** — the full product, design, architecture, and delivery
  blueprint for the local-first "streaming service for short content." This is the authoritative long-form plan.

## Engineering references

- **[semantic-benchmark.md](semantic-benchmark.md)** — reproducible CPU timing and peak-memory procedure for the
  semantic index at 100 / 1,000 / 10,000 captions.
- **[duplicate-calibration.md](duplicate-calibration.md)** — fixture calibration, threshold, and limitations for
  near-duplicate detection.
- **[visible-text-ocr-spike.md](visible-text-ocr-spike.md)** — results of the bounded visible-text OCR spike
  (evaluated, not shipped), including the fixture corpus and reproduction command.

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for setup and the quality gates, and the
[issue templates](../.github/ISSUE_TEMPLATE) to file work.
