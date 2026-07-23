<!-- TODO: add assets/banner.png (project banner) and assets/demo.gif (terminal demo) once available. -->

# ClipFetch

**Netflix for your reels** — collect short-form video once, then search, organize, and watch it like a personal, local-first streaming service.

[![CI](https://github.com/georgyia/ClipFetch/actions/workflows/ci.yml/badge.svg)](https://github.com/georgyia/ClipFetch/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)

```
clipfetch -reels 25
```

That's it. ClipFetch opens a browser session, scrolls your Instagram Reels feed, grabs the next 25 reels the
feed serves you, and downloads them in parallel into a single folder — ready to watch on a flight, on the train,
or anywhere without a connection. Then it lets you catalog, search, categorize, and replay that archive like your
own streaming library.

> **What ships today.** ClipFetch is a **command-line engine** for building and querying a personal short-video
> library — downloading, catalog, search, topics, collections, and more. **ClipFetch Watch**, the local-first
> *streaming interface* on top of that library, is now runnable as a **preview**: start it with `clipfetch web`
> and browse, search, and watch your library in a calm, cinematic UI. The one part still to come is automated
> downloading from *inside* Watch — for now you add clips with the CLI. See the
> [user guide](docs/watch-user-guide.md), the [blueprint](docs/clipfetch-watch-plan.md), and the
> [roadmap](docs/ROADMAP.md).

---

## Contents

- [Quickstart](#quickstart)
- [What ships today](#what-ships-today)
- [Usage](#usage)
- [Deeper capabilities](#deeper-capabilities)
- [The vision — ClipFetch Watch](#the-vision--clipfetch-watch)
- [Platform support](#platform-support)
- [How it works](#how-it-works)
- [Privacy & local-first](#privacy--local-first)
- [Contributing](#contributing)
- [Disclaimer](#disclaimer)
- [License](#license)

---

## Quickstart

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

> **Sign in once.** On the first run ClipFetch opens a browser window and asks you to sign in. The session is
> stored in a local profile (`~/.clipfetch/profile`) and reused on every later run — no passwords are ever seen
> or stored by ClipFetch itself.

```bash
clipfetch -reels 25          # next 25 reels from your feed into ./reels/
clipfetch watch reels        # play the downloaded folder, one clip after another
```

---

## What ships today

| Capability | What it does |
|---|---|
| **One-command downloads** | `clipfetch -reels N` pulls N reels from your personal feed; `@username` targets one account. |
| **Parallel & resumable** | Reels download in parallel while the feed is still scrolling; re-runs skip completed clips and resume partial files. |
| **Offline playback** | `clipfetch watch` plays a downloaded folder in sequence (or `--shuffle`). |
| **Quality control** | `--quality high\|medium\|low` selects the rendition where a choice exists. |
| **Metadata sidecars** | `--metadata` writes normalized JSON (caption, author, hashtags, engagement, duration, time, URL) beside each clip. |
| **Portable catalog** | Every completed clip is recorded in `<output>/.clipfetch/catalog.sqlite3` for fast offline library operations. |
| **Local semantic search** | Optional, offline embedding search over captions/hashtags/transcripts (`semantic` extra). |
| **Topics & collections** | Local, multilingual categorization and saved dynamic filter definitions. |
| **Transcripts & comments** | Optional local speech transcription and opt-in Instagram comment enrichment. |
| **Duplicate reports** | Byte-identical and (optionally) near-duplicate detection — report-only, never destructive. |
| **Cross-browser cookies** | Reuse a Chrome, Firefox, or Safari login with `--import-cookies`. |
| **Self-contained** | No third-party downloader libraries; extraction and download are built on a single dependency (Playwright). |

---

## Usage

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
clipfetch --help                     # all options
```

Re-running the same command tops up the folder — reels already downloaded are skipped.

### Library, search, and organization

```bash
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
clipfetch library collection save reels viral-founders --min-likes 1m \
  --topic entrepreneurship
clipfetch watch reels --collection viral-founders --shuffle
clipfetch library export reels --collection viral-founders --format m3u
clipfetch library export reels --collection viral-founders --format json
clipfetch -reels 25 --min-likes 1m --topic entrepreneurship --scan-limit 250
pip install "clipfetch[transcribe]"  # optional local speech enrichment
clipfetch library enrich transcript reels
clipfetch library enrich transcript reels --topic entrepreneurship --model base
clipfetch library enrich comments reels --max-comments 20 --min-likes 1m
clipfetch library purge-comments reels
clipfetch library duplicates reels --json
pip install "clipfetch[duplicates]"  # optional near-video frame decoding
clipfetch library duplicates reels --include-near
```

The SQLite catalog stores video paths relative to the output folder, so moving the whole folder keeps it
portable. If a catalog is deleted, damaged, or temporarily unwritable, the downloaded videos remain usable;
`clipfetch library index DIR` reconstructs it from supported filenames and any JSON sidecars without renaming or
changing video files.

Metadata is best-effort and platform-dependent: unavailable values are stored as `null`, never guessed as zero.
New sidecars use schema version 2; older unversioned sidecars remain readable. Expiring CDN URLs, authentication
headers, cookies, and raw payloads are excluded.

Library filters combine different dimensions with AND; repeated values within one dimension use OR. Numeric
thresholds accept `k`, `m`, and `b` suffixes (including `1.5m`). A clip with unknown metadata never satisfies a
filter that requires that value, and the human summary reports those exclusions explicitly. `--json` is stable,
unstyled output for scripts.

---

## Optional extras

Each advanced subsystem is an opt-in dependency group. The base install stays Playwright-only.

| Extra | Install | Adds |
|---|---|---|
| `semantic` | `pip install "clipfetch[semantic]"` | Offline embedding search (FastEmbed/ONNX). Python 3.10+. |
| `transcribe` | `pip install "clipfetch[transcribe]"` | Local speech transcripts (Faster-Whisper, CPU int8). |
| `duplicates` | `pip install "clipfetch[duplicates]"` | Near-duplicate frame decoding (PyAV). |
| `cookies` | `pip install "clipfetch[cookies]"` | Windows Chrome AES-GCM cookie decryption. |
| `dev` | `pip install -e ".[dev]"` | ruff + mypy + pytest for contributors. |

---

## Deeper capabilities

### Local semantic search

The optional semantic extra uses FastEmbed/ONNX and the quantized 384-dimensional
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` model. First use downloads about 220 MB into
`~/.cache/clipfetch/fastembed`; after that, indexing and search work offline. The base installation stays
Playwright-only, and metadata commands never import or require FastEmbed. FastEmbed currently requires Python
3.10 or newer.

Semantic documents contain labeled fields for the locally stored caption, normalized hashtags, and any explicitly
generated transcript or retained comment text. Inference runs in-process: captions, queries, and vectors are
never sent to an inference API. Normalized float32 vectors live in the same local SQLite catalog with the model
id, pinned integration revision, input hash, and generation time. Re-indexing is incremental and safely resumes
after interruption.

Semantic similarity is approximate: short or missing captions, slang, and languages with less model coverage can
reduce result quality. Combine search with metadata filters when precision matters. See
[the reproducible CPU benchmark](docs/semantic-benchmark.md) for the 100/1,000/10,000-caption timing and
peak-memory procedure.

### Topics and collections

Topic definitions are library-scoped in `.clipfetch/topics.json`. `topics init` installs starter categories for
entrepreneurship, business, finance, technology, marketing, education, health and fitness, food, travel,
entertainment, and news. Definitions are editable through the CLI without retraining a model. Categorization is
local, multilingual, multi-label, and stores relevance estimates—not factual claims. Manual tags override model
assignments and survive re-categorization until removed with `library tag ... --remove`.

Saved collections persist filter definitions—not video paths—so membership stays dynamic as the catalog changes.
The same filters drive collection show, filtered playback, portable M3U playlists, and stable JSON manifests.
Exports reference relative paths and never copy or modify video files.

Download filters run before submission to the downloader. `COUNT` is the number of accepted clips to attempt;
`--scan-limit` bounds unique feed candidates (default `max(100, COUNT*10)`). The summary reports scanned,
accepted, rejected-by-predicate, and unknown-required-metadata counts. Topic selection uses the same local
definitions/model and never stores rejected CDN URLs. `--dry-run` prints accepted candidates only.

### Local speech transcripts

The separate `transcribe` extra uses Faster-Whisper 1.2.1 with the multilingual `base` model and CPU `int8`
inference by default. Media decoding is provided by packaged PyAV, so a system FFmpeg executable is not normally
required. First use downloads the selected model; runtime and memory grow with model size and clip duration.

Only local video/audio files are decoded. Media and transcript text are never uploaded. ClipFetch stores
normalized transcript text separately from captions, together with language, model identity, source-file hash,
processing time, and status. Runs resume by hash, commit each file independently, and distinguish completed,
silent, unsupported, skipped, and failed files. Transcript changes invalidate only affected semantic vectors and
generated topics; manual topic corrections remain intact. Re-run `library semantic-index` and then
`library categorize` to rebuild only the invalidated generated data.

### Visible text OCR research

Local OCR for titles/subtitles was evaluated but is not shipped. The bounded RapidOCR/ONNX spike reached 1.00
precision but only 0.667 recall because it dropped the mixed-script Unicode fixture; it also required 313–498 MB
of logical dependency files and up to 631 MB peak memory. The fixture corpus, macOS/Linux compatibility results,
thresholds, and reproduction command are in the
[visible-text OCR spike report](docs/visible-text-ocr-spike.md).

### Opt-in Instagram comments

`library enrich comments` is the only workflow that requests comments. It filters the local catalog before
opening the authenticated browser, fetches top-level comments at no more than one request per second, and retains
at most 20 per clip by default (100 hard maximum). Normal downloads, indexing, search, and categorization never
request comments.

Storage is deliberately minimal: normalized comment text, platform comment id, source clip, and retrieval time.
Usernames, profile/user ids, avatars, profile URLs, likes, and raw responses are discarded. Exact duplicate/empty
text is removed and retained semantic text is capped at 4,000 characters per clip. Deleted, disabled,
unavailable, authentication, rate-limit, and failure outcomes are tracked independently so runs can resume
safely.

Fetching comments creates extra Instagram requests and handles volatile user-generated data. Use it only where
permitted by Instagram's terms and your local privacy obligations. Run `library purge-comments DIR` to remove all
stored comment ids/text and invalidate affected generated analysis; manual topics remain. Re-run
`library semantic-index` and `library categorize` afterward to rebuild without comments.

### Safe duplicate reports

`library duplicates` streams complete files through SHA-256 and reports byte-identical groups, even when platform
ids or metadata differ. `--include-near` additionally uses packaged PyAV to sample eight bounded frames plus
duration; it does not require a system FFmpeg executable. Exact and perceptual signatures are cached against file
hash, size, mtime, and algorithm version so unchanged scans avoid hashing/decoding work.

Exact groups are definitive byte matches. Near groups are labeled **probable**, include a distance/confidence,
and require visual review; related captions, topics, and semantic vectors are never treated as duplicate
evidence. Missing, unsupported, and corrupt files are reported independently without aborting the scan. See the
[fixture calibration](docs/duplicate-calibration.md) for the threshold and limitations.

The command is report-only: it never deletes, moves, renames, links, or rewrites a video. Potential recoverable
bytes assume you manually keep the largest member of each group. Review paths and play every probable match
before doing any cleanup yourself.

### Cookie import notes

Firefox import needs no extra package. ClipFetch reads the browser's last-used Chrome profile and supports Secret
Service or KWallet on Linux. Windows Chrome AES-GCM encryption additionally requires
`pip install "clipfetch[cookies]"`; newer app-bound (`v20`) Windows cookies cannot be decrypted outside Chrome,
so use Firefox for those. Safari may require granting the terminal Full Disk Access in macOS System Settings.

### Browser integration test

Normal tests use fakes and do not download or launch a browser. Maintainers can run the opt-in local-fixture
smoke test with `pytest -m integration tests/integration` after `playwright install chromium`, or trigger the
**Browser integration** workflow manually.

---

## The vision — ClipFetch Watch

An algorithmic feed is designed to keep you scrolling. A folder of downloaded files is the opposite problem: it's
inert. **ClipFetch Watch** is the layer in between — a calm, high-quality *streaming interface* over your own
local library, organized around your topics, collections, searches, and viewing history instead of an engagement
loop.

> Collect short-form content once, then search, organize, and watch it like a personal streaming service.

The plan borrows the familiar streaming grammar — a hero feature, curated rails, categories, continue-watching,
and rich detail views — while using an original identity and a player built specifically for vertical, short-form
media. It stays **local-first and single-user**: it binds to `127.0.0.1`, plays files already in your library,
and works without any cloud account.

Design highlights from the blueprint:

- **Reel-native player** — 9:16 media, captions, keyboard/gesture controls, and rapid next/previous navigation.
- **Editorial browsing** — Home rails such as Continue Watching, Recently Added, High-Quality Picks, and per-topic
  channels, deduplicated across rails.
- **Explainable quality** — a *measured* technical tier (resolution/bitrate/codec) kept separate from any
  recommendation score, so "high quality" always means something.
- **Transparent jobs** — downloads and enrichment run in a worker with visible phases, failures, and retries.
- **Accessibility as a release gate** — full keyboard operation, visible focus, reduced-motion support, and
  captions targeted at WCAG 2.2 AA.

Architecturally it reuses everything ClipFetch already does — the catalog, filters, topics, collections, semantic
search, transcripts, and duplicate detection become the content engine beneath a FastAPI `/api/v1` service, a
React + TypeScript frontend, and a background worker.

### Try the preview

Watch is now runnable. It streams a library you built with the CLI — Home rails, Explore, search, collections,
favorites, continue-watching, a vertical player, and quality tiers all work:

```bash
pip install -e ".[web]"        # FastAPI + Uvicorn
npm --prefix web ci && npm --prefix web run build   # build the UI into the package
clipfetch web                  # serves http://127.0.0.1:8000 and opens your browser
```

Point it at a library once via the built-in API docs (`/api/docs`), then browse. The one thing still to come is
an **in-app download source**: the job queue and worker are real, but the live browser-driven downloader is not
wired into Watch yet, so keep using the CLI to add clips. `clipfetch web --demo` runs the full job pipeline with
an offline fake source. Full walkthrough: **[docs/watch-user-guide.md](docs/watch-user-guide.md)**.

📄 **Read the full blueprint:** [docs/clipfetch-watch-plan.md](docs/clipfetch-watch-plan.md) ·
🗺️ **Short roadmap:** [docs/ROADMAP.md](docs/ROADMAP.md) ·
📖 **User guide:** [docs/watch-user-guide.md](docs/watch-user-guide.md)

*ClipFetch Watch is a working product name; it is runnable as a preview (streaming works; automated in-app
downloading is still to come). "Netflix for Reels" describes the browsing quality we're aiming for, not a Netflix
clone or any affiliation with Netflix.*

---

## Platform support

| Source | Status | Notes |
|---|---|---|
| **Instagram Reels** | ✅ Full | Personal feed (`-reels N`) and single accounts (`-reels N @user`). |
| **TikTok** | ⚠️ Experimental | `clipfetch -tiktoks 25`. Extraction is reliable and `--dry-run` lists real video URLs, but TikTok's anti-bot blocks most automated downloads. Use `--dry-run` to get URLs you can hand to another tool. |
| **YouTube Shorts** | ❌ Unavailable | YouTube ciphers its stream URLs (they need a signature computed by YouTube's player JavaScript), which is outside ClipFetch's browser-driver-only design. See [issue #2](https://github.com/georgyia/ClipFetch/issues/2). |

---

## How it works

1. Launches a Chromium instance with a persistent profile dedicated to ClipFetch.
2. Opens `instagram.com/reels/` and listens to the network responses the feed loads.
3. Collects direct video URLs from the feed API responses while auto-scrolling.
4. Streams the videos to disk in parallel worker threads as soon as each URL is found.

For a single account, ClipFetch harvests reel shortcodes from the profile grid and opens each permalink to
capture its playable URL. TikTok clips are fetched through the live browser session because their URLs are bound
to it.

---

## Privacy & local-first

- **Your session, your feed.** ClipFetch uses a dedicated local browser profile you sign in to once; no passwords
  are stored. You may optionally reuse a local Chrome, Firefox, or Safari login.
- **Local by default.** Media, catalog, embeddings, transcripts, and comments all live on your machine. Inference
  runs in-process; nothing is sent to a remote API by default.
- **No secrets in the catalog.** Expiring CDN URLs, authentication headers, cookies, and raw payloads are excluded
  from sidecars and the catalog.
- **No telemetry.** ClipFetch does not phone home.

---

## Contributing

Issues and pull requests are welcome. ClipFetch holds every change — human- or tool-authored — to the same bar:
deterministic behavior, a minimal dependency surface, and green `ruff` / `mypy` / `pytest` gates across supported
Python versions.

- 🛠️ [CONTRIBUTING.md](CONTRIBUTING.md) — dev setup, test philosophy, and the quality gates.
- 📜 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — community expectations.
- 🔒 [SECURITY.md](SECURITY.md) — how to report a vulnerability privately.
- 💬 [SUPPORT.md](SUPPORT.md) — where to ask questions.
- 🧭 [Open tickets](https://github.com/georgyia/ClipFetch/issues) — planned work and good first issues.

The detailed product, design, architecture, and delivery blueprint for the local-first streaming interface is in
the [ClipFetch Watch plan](docs/clipfetch-watch-plan.md).

---

## Disclaimer

ClipFetch is intended for **personal use only** — downloading a handful of reels from your own feed to watch them
offline, exactly as you could in the app.

- Do **not** use it for mass scraping, re-uploading, or redistributing content.
- The videos you download belong to their creators; respect their rights.
- Automated access may violate [Instagram's Terms of Use](https://help.instagram.com/581066165581870). You use
  this tool at your own risk and are responsible for complying with the terms of the services you access and the
  laws that apply to you.
- This project is not affiliated with, endorsed by, or connected to Instagram/Meta — or Netflix.

---

## License

[MIT](LICENSE)
