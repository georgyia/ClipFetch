# ClipFetch Watch — user guide

ClipFetch Watch is a local-first *streaming interface* over the short-form videos you have already
collected with the ClipFetch command-line downloader. It runs entirely on your machine, binds to
`127.0.0.1`, and organizes your library around your topics, collections, searches, and viewing
history instead of an algorithmic feed.

> **Status — preview.** Watch is runnable today. It streams a library you build with the ClipFetch
> CLI: Home rails, Explore, search, collections, favorites, continue-watching, a vertical player,
> quality tiers, and diagnostics all work. What is **not** wired yet is automated downloading from
> inside Watch — the job queue and worker are real, but the live browser-driven download source is
> still to come. Use the CLI to add clips; `clipfetch web --demo` exercises the full job pipeline
> with an offline, deterministic fake source (no network or sign-in).

---

## Contents

- [Installation](#installation)
- [First run](#first-run)
- [Getting around](#getting-around)
- [Playback and keyboard shortcuts](#playback-and-keyboard-shortcuts)
- [Downloads](#downloads)
- [Privacy and local-first](#privacy-and-local-first)
- [Troubleshooting](#troubleshooting)
- [Data locations and migration](#data-locations-and-migration)
- [Reset and uninstall](#reset-and-uninstall)

---

## Installation

Watch is installed from the ClipFetch source tree (there is no published release yet). You need
Python 3.9+ and, to build the interface, Node.js 20+.

```bash
git clone https://github.com/georgyia/ClipFetch.git
cd ClipFetch
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[web]"                              # FastAPI + Uvicorn

# Build the web interface into the package (one time, and after UI updates):
npm --prefix web ci
npm --prefix web run build
```

The build writes the bundle into `clipfetch/webui/`, from where `clipfetch web` serves it. If you
skip the build, `clipfetch web` still runs but serves the API only and tells you so.

---

## First run

Watch **plays a library you already downloaded** — it does not create one for you. If you have never
used ClipFetch, collect some clips first, then index them:

```bash
clipfetch -reels 25            # download 25 reels into ./reels (signs you in once, in a browser)
clipfetch library index reels  # build/refresh the searchable catalog
```

Then start the server:

```bash
clipfetch web                  # serves http://127.0.0.1:8000 and opens your browser
```

Useful flags: `--port 9000`, `--host 0.0.0.0` (exposes it beyond loopback — do this only on a
network you trust), `--no-browser`, and `--demo` (simulated offline downloads).

**Point Watch at your library (first time only).** Watch shows "No active library" until a library is
registered and activated. There is no in-app "add library" form yet, so register it once through the
built-in API docs:

1. Open `http://127.0.0.1:8000/api/docs`.
2. `POST /api/v1/libraries` with a body like `{"display_name": "Reels", "path": "/absolute/path/to/reels"}`
   and copy the `id` from the response.
3. `POST /api/v1/libraries/{id}/activate` with that id.

Reload Watch — Home now shows your rails. Once at least one library is registered, the library
switcher in the header lets you flip between them without touching the API.

---

## Getting around

The primary navigation (a left rail on desktop, a bottom tab bar on mobile) has six destinations:

| Section | What it shows |
|---|---|
| **Home** | Editorial rails — Continue Watching, Recently Added, Favorites, High-Quality Picks, and per-topic channels — deduplicated across rails. |
| **Explore** | Filter the whole library by platform, topic, author, hashtag, and like/view thresholds. Filters are reflected in the URL, so a view is shareable and refresh-safe. |
| **Search** | Text search over captions and hashtags, plus semantic ("by meaning") search when the semantic extra is installed. |
| **Library** | The full catalog, with Recently Added and Favorites views. |
| **Downloads** | Download/enrichment jobs with live progress, phases, retries, and failures. |
| **Settings** | Capabilities, platform support, schema versions, job counts, and a redacted support bundle you can copy into a bug report. |

Opening any clip shows its detail page — caption, author, metadata, an explainable quality tier, and
"more like this" recommendations — with a play button into the vertical player.

---

## Playback and keyboard shortcuts

The player is built for vertical, short-form media: it fills the screen at 9:16, remembers where you
left off (Continue Watching), and moves quickly between clips. Playback position is saved per clip as
you watch.

| Key | Action |
|---|---|
| `Space` or `K` | Play / pause |
| `→` | Seek forward 5 seconds |
| `←` | Seek back 5 seconds |
| `M` | Mute / unmute |
| `N` | Next clip |
| `P` | Previous clip |
| `Esc` | Close the player / go back |

Shortcuts are ignored while a text field is focused, and reduced-motion preferences are respected.

**Posters.** Thumbnails are generated with `ffmpeg` when it is available on your `PATH`; without it,
clips still play — they just show a placeholder instead of a poster.

---

## Downloads

The Downloads page lists jobs and follows their progress live (phases, retries, cancellation, and
sanitized failure reasons). Two things are worth understanding about the current preview:

- **Adding clips still happens through the CLI.** The live, browser-driven download source is not
  wired into Watch yet, so a job enqueued against a real URL stays queued. Download with
  `clipfetch -reels N` (or `-tiktoks N`), then `clipfetch library index <dir>` to make new clips
  appear in Watch.
- **Demo mode shows the pipeline end to end.** Start the server with `clipfetch web --demo` and the
  background worker processes jobs with a deterministic **offline fake source** — no network, no
  sign-in. This is for trying the queue/worker/progress experience, not for real content.

The worker starts and stops with the server, reaps stale job leases so a crash never strands a job,
and only claims work when a source is configured (today: `--demo`).

---

## Privacy and local-first

- **Local by default.** Media, catalog, embeddings, transcripts, and viewing history live on your
  machine. Watch binds to `127.0.0.1`; nothing is sent to a remote service.
- **Your session, your feed.** Downloading uses a dedicated local browser profile you sign in to
  once. No passwords are stored, and third-party cookies are never exposed to the interface.
- **No secrets in the catalog.** Expiring CDN URLs, auth headers, cookies, and raw payloads are kept
  out of the catalog, sidecars, and logs. The API addresses clips, media, and posters by id — it
  never hands the browser a filesystem path or an expiring URL.
- **Redacted diagnostics.** The support bundle on the Settings page contains only versions, counts,
  enums, and capability flags — no paths, library names, captions, or URLs.
- **No telemetry.** ClipFetch does not phone home.

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Watch loads but says "serving the API only" | The UI bundle is not built. Run `npm --prefix web run build`, then restart `clipfetch web`. |
| `The web interface needs extra packages` | Install the web extra: `pip install -e ".[web]"`. |
| "No active library" on Home | Register and activate a library once via `/api/docs` (see [First run](#first-run)). |
| Home is empty after activating | The catalog has no clips yet. Download with the CLI and run `clipfetch library index <dir>`. |
| Address already in use | Another process holds the port. Start with `--port 9000` (or free port 8000). |
| A download job stays "queued" | Expected in the preview unless you started with `--demo` — the live download source is not wired yet. Add clips with the CLI. |
| Clips play but show no thumbnail | `ffmpeg` is not on your `PATH`. Install it to enable poster generation; playback is unaffected. |
| Semantic search is unavailable | Install the semantic extra: `pip install -e ".[semantic]"` (Python 3.10+). The Settings page shows which capabilities are active. |

If you file a bug, include the **support bundle** from the Settings page — it is safe to share.

---

## Data locations and migration

- **Per-library catalog:** `<library>/.clipfetch/catalog.sqlite3` (plus topics/collections sidecars).
  This is the same catalog the CLI writes, so a library you built with ClipFetch works in Watch as-is.
- **Device-local app state** (registered libraries, playback progress, favorites, jobs):
  - macOS: `~/Library/Application Support/clipfetch/appstate.sqlite3`
  - Linux: `${XDG_DATA_HOME:-~/.local/share}/clipfetch/appstate.sqlite3`
  - Windows: `%LOCALAPPDATA%\clipfetch\appstate.sqlite3`

**Migrations are forward-only and automatic.** Both databases carry a schema version and apply
additive migrations atomically when opened, so an older library upgrades in place the first time
Watch (or the CLI) touches it. There is no downgrade path — back up a library folder before trying a
much newer build if you may need to return to an older one.

---

## Reset and uninstall

- **Forget a library** (without deleting its files): `DELETE /api/v1/libraries/{id}` via `/api/docs`,
  or delete the app-state database to clear all registrations, playback progress, and favorites.
- **Full reset of device state:** delete the `clipfetch/appstate.sqlite3` file at the path above. Your
  downloaded media and per-library catalogs are untouched.
- **Uninstall:** `pip uninstall clipfetch` and remove the virtual environment. Your library folders
  remain yours.
