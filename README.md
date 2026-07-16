# ClipFetch

[![CI](https://github.com/georgyia/ClipFetch/actions/workflows/ci.yml/badge.svg)](https://github.com/georgyia/ClipFetch/actions/workflows/ci.yml)

Download short-form videos from your feed to watch offline — straight from the terminal.

```
clipfetch -reels 25
```

That's it. ClipFetch opens a browser session, scrolls your Instagram Reels feed, grabs the
next 25 reels the feed serves you, and downloads them in parallel into a single folder —
ready to watch on a flight, on the train, or anywhere without a connection.

## Features

- **One command** — `clipfetch -reels N` downloads N reels from your personal Reels feed.
- **Accounts too** — `clipfetch -reels N @username` grabs a specific account's reels.
- **Fast** — reels are downloaded in parallel while the feed is still being scrolled.
- **Interactive** — live per-download bars, transferred-size totals, and a rough ETA.
- **Watch offline** — `clipfetch watch` plays a downloaded folder one clip after another.
- **Picks up where it left off** — re-running skips completed reels and resumes partial files.
- **Quality control** — `--quality high|medium|low` chooses the rendition.
- **Metadata sidecars** — `--metadata` writes normalized, human-readable JSON beside each
  clip: caption, author, hashtags, engagement counts, duration, publication time and URL.
- **Portable local catalog** — every completed clip is recorded automatically in
  `<output>/.clipfetch/catalog.sqlite3` for fast offline library operations.
- **Self-contained** — no third-party downloader libraries; the extraction and download
  logic is built from scratch on top of a single dependency (Playwright, the browser driver).
- **Your session, your feed** — uses a dedicated local browser profile you sign in to once;
  no passwords stored. Optionally reuse a local Chrome, Firefox, or Safari login.
- **More platforms** — TikTok is available (`-tiktoks N`, experimental — see below).

## Installation

Requires Python 3.9+.

```bash
pip install git+https://github.com/georgyia/ClipFetch.git
playwright install chromium
```

Or from a clone:

```bash
git clone https://github.com/georgyia/ClipFetch.git
cd ClipFetch
pip install -e .
playwright install chromium
```

## Usage

> **You must be signed in to Instagram first.** On the first run ClipFetch opens a browser
> window and asks you to sign in once. The session is stored in a local profile
> (`~/.clipfetch/profile`) and reused on every later run — no passwords are ever seen or
> stored by ClipFetch itself.

```bash
clipfetch -reels 25                  # next 25 reels from your feed into ./reels/
clipfetch -reels 10 @nasa            # 10 reels from a specific account
clipfetch -reels 10 --out ~/clips    # choose the output folder
clipfetch -reels 5 --quality low     # smaller files where a choice exists
clipfetch -reels 5 --dry-run         # only list the video URLs, download nothing
clipfetch -reels 25 --metadata       # also save caption/author/likes as a .json per clip
clipfetch -reels 25 --import-cookies firefox  # Firefox on macOS/Linux/Windows
clipfetch -reels 25 --import-cookies chrome   # Chrome on macOS/Linux/Windows
clipfetch -reels 25 --import-cookies safari   # Safari on macOS
clipfetch watch reels                # play the downloaded folder in sequence
clipfetch watch reels --shuffle      # …in random order
clipfetch library index reels        # rebuild/reconcile the portable local catalog
clipfetch library list reels --min-likes 1m --hashtag entrepreneurship
clipfetch library list reels --author nasa --author spacex --sort views --json
clipfetch library info reels ABC123  # inspect one cataloged clip
pip install "clipfetch[semantic]"    # optional; Python 3.10+
clipfetch library semantic-index reels
clipfetch library search reels "entrepreneurship and startup advice"
clipfetch library search reels "emprendimiento" --min-likes 1m
clipfetch topics init reels
clipfetch topics add reels climate-tech --description "climate technology" \
  --example "clean energy startup"
clipfetch library categorize reels
clipfetch library list reels --topic entrepreneurship
clipfetch library tag reels ABC123 --topic entrepreneurship
clipfetch --help                     # all options
```

Re-running the same command tops up the folder — reels already downloaded are skipped.

The SQLite catalog stores video paths relative to the output folder, so moving the whole
folder keeps it portable. If a catalog is deleted, damaged, or temporarily unwritable,
the downloaded videos remain usable; `clipfetch library index DIR` reconstructs it from
supported filenames and any JSON sidecars without renaming or changing video files.

Metadata is best-effort and platform-dependent: unavailable values are stored as `null`,
never guessed as zero. New sidecars use schema version 2; older unversioned sidecars remain
readable. Expiring CDN URLs, authentication headers, cookies, and raw payloads are excluded.

Library filters combine different dimensions with AND; repeated values within one dimension
use OR. Numeric thresholds accept `k`, `m`, and `b` suffixes (including `1.5m`). A clip with
unknown metadata never satisfies a filter that requires that value, and the human summary
reports those exclusions explicitly. `--json` is stable, unstyled output for scripts.

### Local semantic search

The optional semantic extra uses FastEmbed/ONNX and the quantized 384-dimensional
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` model. First use downloads
about 220 MB into `~/.cache/clipfetch/fastembed`; after that, indexing and search work
offline. The base installation stays Playwright-only, and metadata commands never import
or require FastEmbed. FastEmbed currently requires Python 3.10 or newer.

Semantic documents contain only the locally stored caption and normalized hashtags.
Inference runs in-process: captions, queries, and vectors are never sent to an inference
API. Normalized float32 vectors live in the same local SQLite catalog with the model id,
pinned integration revision, input hash, and generation time. Re-indexing is incremental
and safely resumes after interruption.

Semantic similarity is approximate: short or missing captions, slang, and languages with
less model coverage can reduce result quality. Combine search with metadata filters when
precision matters. See [the reproducible CPU benchmark](docs/semantic-benchmark.md) for
the 100/1,000/10,000-caption timing and peak-memory procedure.

Topic definitions are library-scoped in `.clipfetch/topics.json`. `topics init` installs
starter categories for entrepreneurship, business, finance, technology, marketing,
education, health and fitness, food, travel, entertainment, and news. Definitions are
editable through the CLI without retraining a model. Categorization is local, multilingual,
multi-label, and stores relevance estimates—not factual claims. Manual tags override model
assignments and survive re-categorization until removed with `library tag ... --remove`.

Firefox import needs no extra package. Modern Windows Chrome encryption additionally
requires `pip install "clipfetch[cookies]"`; Safari may require granting the terminal
Full Disk Access in macOS System Settings.

### Browser integration test

Normal tests use fakes and do not download or launch a browser. Maintainers can run the
opt-in local-fixture smoke test with `pytest -m integration tests/integration` after
`playwright install chromium`, or trigger the **Browser integration** workflow manually.

### Other platforms

- **TikTok** (`clipfetch -tiktoks 25`) — *experimental*. Extraction is reliable and
  `--dry-run` lists real video URLs, but TikTok's anti-bot blocks most automated
  downloads. Use `--dry-run` to get URLs you can hand to another tool.
- **YouTube Shorts** — not available: YouTube ciphers its stream URLs (they need a
  signature computed by YouTube's player JavaScript), which is outside ClipFetch's
  browser-driver-only design. See [issue #2](https://github.com/georgyia/ClipFetch/issues/2).

## How it works

1. Launches a Chromium instance with a persistent profile dedicated to ClipFetch.
2. Opens `instagram.com/reels/` and listens to the network responses the feed loads.
3. Collects direct video URLs from the feed API responses while auto-scrolling.
4. Streams the videos to disk in parallel worker threads as soon as each URL is found.

For a single account, ClipFetch harvests reel shortcodes from the profile grid and opens
each permalink to capture its playable URL. TikTok clips are fetched through the live
browser session because their URLs are bound to it.

## Disclaimer

ClipFetch is intended for **personal use only** — downloading a handful of reels from your
own feed to watch them offline, exactly as you could in the app.

- Do **not** use it for mass scraping, re-uploading, or redistributing content.
- The videos you download belong to their creators; respect their rights.
- Automated access may violate [Instagram's Terms of Use](https://help.instagram.com/581066165581870).
  You use this tool at your own risk and are responsible for complying with the terms of
  the services you access and the laws that apply to you.
- This project is not affiliated with, endorsed by, or connected to Instagram/Meta.

## Contributing

Issues and pull requests are welcome — see the
[open tickets](https://github.com/georgyia/ClipFetch/issues) for planned work.

## License

[MIT](LICENSE)
