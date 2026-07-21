# 0001 — Monorepo and runtime boundaries for ClipFetch Watch

**Status:** Accepted
**Date:** 2026-07-22
**Deciders:** ClipFetch maintainers
**Related:** [ClipFetch Watch plan](../clipfetch-watch-plan.md), [ROADMAP](../ROADMAP.md)

## Context

ClipFetch today is a single-dependency (Playwright) Python CLI with a reusable domain layer:
`clipfetch/library.py` (`ClipFilter`, `query_library`, `record_to_dict`), `clipfetch/catalog.py`
(the versioned per-library SQLite `Catalog`), and focused feature modules for collections, topics,
semantic search, transcripts, comments, and duplicates. The CLI in `clipfetch/cli.py` is the only
consumer of that layer, and it still mixes argument parsing, orchestration, and presentation
(notably in `cli._run` and `cli._run_library`).

We are adding **ClipFetch Watch** — a local-first "streaming service for short content" web interface
over the same library. That work needs an HTTP API, a browser frontend, background download/enrichment
jobs, and device-specific state (playback, favorites), none of which exist yet. Before writing that
code we must decide where it lives and how the pieces are allowed to depend on one another, so the
codebase does not collapse into one coupled application.

## Decision

1. **Build ClipFetch Watch in this repository as a monorepo.** The Python package keeps the content
   engine; a `web/` frontend and new backend packages (`clipfetch/api/`, `clipfetch/services/`,
   `clipfetch/jobs/`) are added alongside it. We do **not** split repositories for the first release.

2. **Introduce a reusable service layer** (`clipfetch/services/`) beneath both the CLI and the future
   API. Services take validated domain values and return typed results — never argparse namespaces or
   FastAPI objects.

3. **Expose a versioned local HTTP API** (`/api/v1`, FastAPI) as an optional extra. The frontend talks
   to Python only through this API.

4. **Run long or blocking work in a separate worker process** backed by a SQLite job queue — never in
   the API event loop.

5. **Separate two databases.** The portable per-library `catalog.sqlite3` keeps content facts; a
   separate application-state database keeps device-specific state (registered libraries, playback,
   favorites, jobs). A copied library therefore stays portable.

6. **Serve media by catalog clip ID only,** via HTTP byte-range requests against the original MP4 —
   no transcoding pipeline, and no path query parameters, for the MVP.

7. **Bind to `127.0.0.1` by default.** Remote/LAN access is a later decision with its own threat model.

### Boundary rules

These rules are the point of this ADR and are enforced in review:

1. API routes call service functions; they do not call CLI argument handlers.
2. CLI commands call the same service functions; they do not make loopback HTTP requests.
3. Services do not import FastAPI or any frontend concept.
4. The frontend reaches Python only through `/api/v1`.
5. The frontend never receives a filesystem path it can turn into an arbitrary file request.
6. Catalog reads/writes go through the existing `Catalog` abstraction or a deliberate extension of it.
7. Long-running or blocking jobs execute outside the API event loop.
8. Optional capabilities (semantic, transcription, duplicates) return explicit capability states rather
   than crashing at import time.
9. API models are public contracts and do not leak internal dataclasses by accident.
10. Generated frontend artifacts never overwrite hand-written source.

## Consequences

**Easier**

- One place to change a contract, its fixtures, and its tests together.
- The CLI keeps working throughout, because it and the API share one service layer.
- The portable-library promise is preserved: device state lives in a separate database.
- A future desktop or remote client can reuse the same versioned API.

**Harder / accepted costs**

- The Python package gains an optional web dependency group and a bundled frontend build step; the base
  install stays Playwright-only.
- Stacked/ordered changes are needed while the service layer is extracted before the API consumes it.
- We must keep the two database schemas versioned independently.

## When to revisit

Split the frontend into its own repository only when at least one is true: it deploys independently to a
public origin; it has a separate team and release cadence; multiple backends must serve it; the Python
package must release with no Node build responsibility; or a public API has stabilized enough for
independently versioned clients.

## Alternatives considered

- **Separate frontend repository now.** Rejected: it makes contract changes, shared fixtures, and E2E
  verification harder before the product loop is even validated.
- **Microservices / cloud transcoding / adaptive streaming from day one.** Rejected: large operational
  cost before the local browse-to-play experience is proven. HLS/transcoding remains a later, separate
  phase gated on a concrete requirement (remote playback, multiple bitrates, incompatible codecs).
- **Do the web work inside the CLI process.** Rejected: Playwright, downloads, transcription, and media
  analysis are blocking and failure-prone; mixing them into request handling would make the UI's health
  boundary meaningless.
- **One shared database for content and device state.** Rejected: it would put device-specific watch
  state into the portable catalog and break the "copy the folder" portability guarantee.
