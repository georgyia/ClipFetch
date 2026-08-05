# ClipFetch Watch — user guide

ClipFetch Watch is a local-first *streaming interface* over the short-form videos you have already
collected with the ClipFetch command-line downloader. It runs entirely on your machine, binds to
`127.0.0.1`, and organizes your library around your topics, collections, searches, and viewing
history instead of an algorithmic feed.

> **Status — preview.** Watch is runnable today: Home rails, Explore, search, collections,
> favorites, continue-watching, a vertical player, quality tiers, and diagnostics all work — and so
> does **downloading from inside Watch**. Connect Instagram once and the background worker drives
> the same browser stack the CLI uses, with live progress, retries, and cancellation
> ([Downloads](#downloads)). Instagram is the supported source: TikTok is experimental and
> anti-botted, YouTube Shorts downloading is unavailable, and UI-triggered sign-in needs a local
> display. `clipfetch web --demo` swaps in an offline, deterministic fake source (no network or
> sign-in) for trying the job pipeline itself.

---

## Contents

- [Installation](#installation)
- [First run](#first-run)
- [Getting around](#getting-around)
- [Playback and keyboard shortcuts](#playback-and-keyboard-shortcuts)
- [Downloads](#downloads)
- [Accessibility](#accessibility)
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

Opening any clip shows its detail page — an ambient backdrop built from the clip's own poster, the
caption, author, metadata as chips, an explainable quality tier, and "more like this"
recommendations — with a prominent **Play** into the vertical player. Playing from a clip's detail
page seeds the queue with that clip's topic, so *next* continues along something related.

### Jump anywhere with ⌘K

Press **⌘K** (**Ctrl+K** on Windows and Linux), or click the search box in the header, to open the
command palette. It searches every destination at once:

- **routes** — Home, Explore, Search, Library, Downloads, Settings
- **topics and collections** in your library, with clip counts
- **actions** — add reels, add a library, connect an account, switch theme, show keyboard shortcuts
- **clips** — up to five live matches as you type
- **recent searches**, when the box is empty

Arrow keys move the selection, `Enter` runs it, `Esc` closes. Anything the palette cannot match
offers *Search for "…"* as a fallback, which opens the full search page.

### Filtering in Explore

Explore's facets are chips: sort, topic, platform, and minimum likes, plus a creator field. The bar
stays pinned while results scroll, so you never have to scroll back up to change a filter. Whatever
is currently narrowing the view appears as a row of **active filter** chips that clear individually,
and **Clear all** resets the filters while keeping your chosen sort order.

Every filter lives in the URL, so a filtered view is shareable and refresh-safe — and **Play all**
or **Shuffle** turns that exact set into a player queue.

### Collections: saved filters, hand-picked clips, or both

A collection can work two ways, and one collection can do both at once:

- **Filtered** — the collection stores a *query* (topic, platform, minimum likes). Membership is
  re-evaluated every time you open it, so it keeps up as your library grows.
- **Added by hand** — you put specific clips in it. Hover any card and use the folder-plus control,
  or press **Select** on a grid, tick several clips, and use **Add to collection** in the bar that
  appears. A clip you added stays in the collection even if it does not match the filter.

Create either kind on the **Collections** page, or straight from the add-to-collection dialog:
naming a new collection there creates one with **no filter**, so it holds exactly what you put in it
and never grows on its own.

Open a collection to browse it. Clips you added by hand carry a small **✕** — that removes them from
the collection, never from your library. Clips the *filter* matched have no such control: they leave
when they stop matching the filter, which you change by editing the collection.

Collections are stored with the library (`.clipfetch/collections.json`), so they travel with it if
you copy the folder to another machine — and the CLI sees the same collections:
`clipfetch library collection add reels keepers --clip ABC123`.

### Reading a clip's transcript and comments

If you enriched a clip with `clipfetch library enrich transcript` or `… enrich comments`, its detail
page carries what that produced:

- **Transcript** — the text, the language and the model that produced it (so you can tell *what*
  transcribed it), a **Copy** action, and a find-within box that highlights every match and counts
  them. Text search already looks inside transcripts, so this is where you see the words a result
  actually matched on.
- **Comments** — what was captured, with the time it was captured. These are a **local snapshot**,
  not a live view: they are the comments as they were when fetched, and the panel says so.

Neither panel appears for a clip that has no enrichment — instead, the clip page offers **Add
transcript** and **Fetch comments**. Those run as real jobs on the same queue as downloads, so you
get progress, retries, and cancellation on the Downloads page, and the result appears on the clip
page as soon as it lands.

Both have prerequisites, and Watch checks them *before* queueing anything rather than letting a job
fail at the front of the queue:

- **Transcripts** need the local speech extra: `pip install "clipfetch[transcribe]"`. Without it the
  button tells you exactly that.
- **Comments** need a signed-in Instagram session — connect the account in Settings first.

If a run finished without producing anything, the panel explains why in plain terms — no speech
found, comments turned off by the creator, the post was deleted, rate-limited, and so on.

### Exporting a view

Any collection, and any filtered Explore view, has an **Export** control next to *Play all*. It
offers two formats and tells you how many clips it covers first:

- **Playlist (`.m3u`)** — opens in VLC, mpv, or anything else that reads a playlist.
- **Manifest (`.json`)** — the metadata for every clip, stable enough to keep or diff.

Exports cover the **whole** match set, not just the pages you have scrolled through, and both use
library-relative paths — so a playlist keeps working after you move the library folder, and nothing
in the file names your machine. This is the same output as
`clipfetch library export reels --collection NAME --format m3u`.

### When a clip's file goes missing

ClipFetch never drops what it knows about a clip just because the file disappeared — if you move a
folder, your captions, topics, and transcripts should survive the move. The clip is marked
**unavailable** instead, and it stops appearing in browse views and playback.

**Library → Check for missing media** lists those clips, with the path each one used to live at so
you can go looking for it. Two ways out:

- **Rescan library** — the usual fix. A folder you moved back, or files added out of band, are
  found again and the rows disappear.
- **Forget** — for records whose file is gone for good. This removes what the catalog knows about
  the clip. It **never deletes a file**, and the server re-checks the disk before removing
  anything, so a row that came back while you were reading is kept rather than dropped. If a
  forgotten file ever returns, `clipfetch library index` re-creates the clip from it.

### Insights: what you actually watch

**Library → See what you actually watch** summarizes the library and your viewing: how many clips
you hold, how much of it you have opened, the creators and topics you return to, and the last 30
days of activity. Every figure links to the clips behind it.

Two things it deliberately is not. It is not tracking: everything is counted on demand from the
playback positions the player already saves on this device, opening the page records nothing, and
no number leaves your machine. And it is not a scoreboard — there are no streaks or goals. The one
nudge is towards the clips you collected and never opened, because that is the only figure with an
obvious next step.

**Watch time** is the furthest point you reached in each clip, added up: a clip you finished counts
its full length once, one you abandoned counts where you stopped. Rewatching does not multiply it,
because nothing records whether a second play ran to the end — that number would be invented rather
than measured. Rewatches do show up in the play counts.

### Choosing a theme

Watch ships a refined dark theme and a light theme. **Settings → Appearance** offers *System*,
*Light*, and *Dark*; you can also switch from the header or the command palette. *System* follows
your operating system and updates live when it changes. Your choice is stored in the browser and
applied before the first paint, so there is no flash of the wrong theme on load.

---

## Playback and keyboard shortcuts

The player is built for vertical, short-form media: it fills the screen at 9:16, remembers where you
left off (Continue Watching), and moves quickly between clips. Playback position is saved per clip as
you watch.

**Anywhere in the app:**

| Key | Action |
|---|---|
| `⌘K` / `Ctrl+K` | Open the command palette |
| `?` | Show the keyboard-shortcuts sheet |

**In the player:**

| Key | Action |
|---|---|
| `Space` or `K` | Play / pause |
| `→` | Seek forward 5 seconds |
| `←` | Seek back 5 seconds |
| `M` | Mute / unmute |
| `N` | Next clip |
| `P` | Previous clip |
| `S` | Toggle shuffle |
| `Q` | Toggle the up-next queue |
| `F` | Full screen |
| `Esc` | Leave full screen, then close the player |

Bare-key shortcuts are ignored while a text field is focused, so typing `?` into a search box types
a question mark. `⌘K` is the exception — it works from inside a text field too, because a modifier
chord is unambiguous.

The control bar fades away while a clip is playing and returns the moment you move the pointer or
press a key. It never hides while the video is paused, while the up-next queue is open, or while
your focus is inside the controls — and it never hides at all if you have reduced motion enabled.

The scrubber shows how much of the clip has buffered and, on hover, the exact time under the
pointer. Up-next is a sheet with poster thumbnails you can jump straight to.

Reduced-motion preferences are respected throughout: page transitions, card reveals, and the
ambient glow behind the player are all disabled rather than merely shortened.

**Posters.** A thumbnail is generated with `ffmpeg` for each clip as it downloads, when `ffmpeg` is
on your `PATH`; without it, clips still play — they just show a placeholder instead of a poster.
Settings → Capabilities shows whether **Thumbnails** are available in your environment.

---

## Downloads

The Downloads page lists jobs and follows their progress live (phases — including a **posters**
step — retries, cancellation, and sanitized failure reasons).

- **Add clips from inside Watch.** First connect your account: Settings (or the Downloads page)
  → **Connect Instagram** opens a browser window once for you to sign in; downloads then run
  headless with that saved session. Then use the **Add reels** form to download your feed or a
  single `@account` at a chosen count and quality. New clips appear automatically — no manual
  re-index. If a job fails with *sign-in required*, the row offers a **Connect account** action.
- **Instagram-first.** Instagram is fully supported. TikTok is experimental and anti-botted (use
  the CLI's `-tiktoks N`); YouTube Shorts downloading is unavailable. The download form and platform
  matrix surface these limits — nothing implies an unsupported platform works.
- **Headless/remote servers.** UI-triggered sign-in needs a local display. When the server has no
  display, connecting reports that clearly; sign in with the CLI instead, then downloads work.
- **Demo mode shows the pipeline end to end.** Start the server with `clipfetch web --demo` and the
  background worker processes jobs with a deterministic **offline fake source** — no network, no
  sign-in. This is for trying the queue/worker/progress experience, not for real content.

The worker starts and stops with the server, reaps stale job leases so a crash never strands a job,
and only claims work when a source is configured (the real Instagram source by default, or the
fake source under `--demo`).

---

## Accessibility

Watch is built to WCAG 2.2 AA: full keyboard operation with visible focus, announced route changes,
labelled controls, 44px targets, and both themes contrast-checked in the test suite. Reduced-motion
preferences disable page transitions, card reveals, the player's ambient glow, and control
auto-hide — rather than merely shortening them.

The full picture, including verification and the gaps that are *not* claimed (no timed captions in
the player yet), is in **[accessibility.md](accessibility.md)**.

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
| "No active library" on Home | Add and activate a library from the **Library** page (or via `/api/docs`); see [First run](#first-run). |
| Home is empty after activating | The catalog has no clips yet. Connect your account and use **Add reels** on the Downloads page, or download with the CLI and **Rescan** the library. |
| Address already in use | Another process holds the port. Start with `--port 9000` (or free port 8000). |
| A download job stays "queued" | The worker needs a source. Connect your account (Downloads → **Connect Instagram**), or start with `--demo` to run the offline fake source. |
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
