# Contributing to ClipFetch

Thanks for your interest in improving ClipFetch. Contributions of all sizes are welcome — bug reports, docs,
tests, and code.

This project holds every change to the same bar, no matter who or what wrote it. The goal is boring, dependable
engineering: **deterministic behavior, a minimal dependency surface, and green quality gates on every supported
Python version.** A clever patch that widens the dependency footprint or weakens a test is not an improvement
here.

By participating you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Development setup

Requires Python 3.9+.

```bash
git clone https://github.com/georgyia/ClipFetch.git
cd ClipFetch
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

The base package depends only on Playwright. The browser binary is **only** needed for the opt-in integration
smoke test:

```bash
playwright install chromium
```

Optional feature groups are installed as extras when you work on those subsystems:

| Working on… | Install |
|---|---|
| Semantic search | `pip install -e ".[semantic]"` (Python 3.10+) |
| Transcripts | `pip install -e ".[transcribe]"` |
| Duplicate detection | `pip install -e ".[duplicates]"` |
| Windows cookie decryption | `pip install -e ".[cookies]"` |

---

## Quality gates

Every pull request must pass the same three checks CI runs. Run them locally before pushing:

```bash
ruff check .          # lint + import order
mypy                  # static type check (config in pyproject.toml)
python -m pytest -q   # test suite
```

CI runs `ruff` + `mypy` on Python 3.13 and the full test suite on **Python 3.9, 3.11, and 3.13**. Because 3.9 is
the floor, code must not rely on newer syntax that evaluates incompatibly on 3.9. When you use modern typing
forms (`X | Y`, built-in generics, etc.), add `from __future__ import annotations` at the top of the module so
annotations stay compatible.

---

## Test philosophy: fakes, not browsers

The normal test suite **never launches a browser or touches the network.** It drives the code with fakes and a
local HTTP server, so `python -m pytest -q` is fast, deterministic, and offline. Please keep it that way — new
tests should not require credentials, live third-party sites, or downloaded models.

Expensive, environment-dependent behavior lives behind **opt-in markers** that are excluded from the default run
(`addopts = -m 'not integration'`):

| Marker | Purpose | Run it |
|---|---|---|
| `integration` | Real Chromium against local fixtures | `pytest -m integration tests/integration` |
| `semantic_integration` | Downloads/runs the real embedding model | `pytest -m semantic_integration` |
| `transcription_integration` | Downloads/runs Faster-Whisper | `pytest -m transcription_integration` |
| `duplicate_integration` | Perceptual-hash calibration on transformed video | `pytest -m duplicate_integration` |

If your change touches a subsystem with an opt-in suite, run the matching marker locally and say so in the PR.

---

## Project layout

ClipFetch is a flat Python package under `clipfetch/`. The reusable domain layer (catalog, queries, collections,
topics, semantic, transcription, comments, duplicates) is deliberately independent of the CLI — see the module
map and service boundaries in [docs/clipfetch-watch-plan.md §7.3](docs/clipfetch-watch-plan.md). When you add
behavior, prefer putting it in the domain modules and calling it from `cli.py`, rather than embedding logic in
argument parsing.

Guiding rules:

- **Keep secrets out of persisted data.** Expiring CDN URLs, cookies, auth headers, and raw payloads must never
  be written to the catalog, sidecars, or logs.
- **Fail honestly.** Unknown metadata is `null`, never a guessed `0`. Report skipped/failed items instead of
  hiding them.
- **Additive, versioned migrations.** Catalog schema changes go through the existing `MIGRATIONS`/`_migrate`
  framework in `clipfetch/catalog.py` and must let older libraries open.

---

## Submitting changes

1. **Open or find an issue** using the [templates](.github/ISSUE_TEMPLATE) so scope is agreed before large work.
2. **Branch** from `main`.
3. **Keep commits focused** and revert-safe; write imperative commit subjects ("Add …", "Fix …").
4. **Run the gates** (`ruff`, `mypy`, `pytest`) and any relevant opt-in marker.
5. **Update docs** and, when you touch behavior, add tests.
6. **Open a pull request** and fill in the [PR template](.github/PULL_REQUEST_TEMPLATE.md) checklist.

A change is done only when the behavior is implemented, tests pass (3.9 included where Python is touched), docs
are updated, and no secrets, absolute paths, or expiring URLs leak. Small, reviewable PRs are far more likely to
land quickly than large ones.

---

## Reporting bugs and requesting features

- **Bugs:** [open a bug report](https://github.com/georgyia/ClipFetch/issues/new/choose) with reproduction steps,
  expected vs. actual behavior, and your OS/Python version.
- **Features:** describe the problem first, then the proposed solution. Roadmap-scale ideas for the streaming
  interface should reference [docs/ROADMAP.md](docs/ROADMAP.md).
- **Security:** do **not** open a public issue — follow [SECURITY.md](SECURITY.md).

Thank you for helping keep ClipFetch small, correct, and pleasant to use.
