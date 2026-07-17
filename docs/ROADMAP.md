# Roadmap

> **Status.** ClipFetch — the command-line downloader, catalog, and library engine — **ships today.**
> **ClipFetch Watch** — the local-first *streaming interface* over that library — is **in design**. This page is
> the short version; the authoritative plan is [clipfetch-watch-plan.md](clipfetch-watch-plan.md).

## The north star

Turn a folder of downloaded short videos into an intentional viewing library: a calm, cinematic, local-first
streaming interface organized around your own topics, collections, searches, and viewing history — not an
algorithmic feed. It stays single-user and binds to `127.0.0.1`; it plays files already in your ClipFetch
library and works without any cloud account.

The streaming layer **reuses the existing engine** (catalog, filters, topics, collections, semantic search,
transcripts, duplicates) beneath a FastAPI `/api/v1` service, a React + TypeScript frontend, and a background
worker. See the service ↔ module map in
[clipfetch-watch-plan.md §7.3](clipfetch-watch-plan.md).

## Delivery phases

Each phase is independently releasable, with tests and docs included.

| Phase | Focus |
|---|---|
| **0 · Foundations** | ADRs (monorepo, API, app-state, worker, media delivery), supported versions, and a deterministic offline fixture library. |
| **1 · Service layer** | Extract catalog/topics/collections/search services from the CLI; keep CLI behavior stable. |
| **2 · Read-only API** | FastAPI app, bootstrap/clips/topics/collections/search endpoints, and a safe byte-range media/poster endpoint. |
| **3 · Frontend foundation** | Vite + React + TypeScript shell, design tokens, accessible primitives, responsive navigation. |
| **4 · Browse-to-play slice** | Home hero + rails → clip detail → vertical player with range playback and next/previous. |
| **5 · Library state** | App-state DB, playback progress + Continue Watching, favorites, Explore filters, search UI, collection CRUD. |
| **6 · Download jobs** | SQLite-backed worker, job leases/retries/cancellation, download form, SSE progress. |
| **7 · Media & quality** | Media probing (migration 8), poster generation, explainable technical quality tiers. |
| **8 · Polish** | Accessibility (WCAG 2.2 AA), reduced motion, large-library performance, diagnostics. |
| **9 · Packaging** | Bundle the frontend, `clipfetch web` launch, worker supervision, install/upgrade docs. |

## First vertical slice

The first milestone is one thin end-to-end experience, not "all backend" or "all design system":

> Open a fixture library → see Recently Added → open clip details → play and seek a local video → return to the
> same rail position.

This validates the hardest boundary — catalog → API → in-browser media playback — before investing in every
screen.

## MVP scope

- One active local library.
- Editorial Home rails; topics and collections browsing.
- Text search and optional semantic search.
- Detail view and a reel-native vertical player with range-based local playback.
- Playback progress and favorites.
- URL submission with transparent job progress.
- Media probing, posters, and explainable technical quality.
- Responsive, keyboard-accessible interface.
- Bundled local launch (`clipfetch web`).

## Later, only after validation

Multiple libraries, batch import, richer collection editor, transcript time-linking, local recommendation tuning,
a native desktop shell, authenticated LAN/remote mode, cross-device sync, and HLS/transcoding for incompatible
media. Each of these changes the threat model or operating cost and is **not** a free extension of the local MVP.

## Tracking

The full backlog (39 issues, grouped Foundation → API/media → Frontend → Core experience → Jobs → Quality) is in
[clipfetch-watch-plan.md §21](clipfetch-watch-plan.md). Ready-to-file drafts live in
[`.issue-drafts/`](../.issue-drafts). File roadmap work with the **ClipFetch Watch task** issue template.
