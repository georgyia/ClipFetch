# Architecture Decision Records

This directory holds the Architecture Decision Records (ADRs) for ClipFetch and ClipFetch Watch.

An ADR captures a single significant decision — its context, the choice made, and the consequences — so
that future contributors can understand *why* the code is shaped the way it is without archaeology.

## Format

Each ADR is a numbered Markdown file (`NNNN-short-title.md`) with these sections:

- **Status** — Proposed, Accepted, Superseded, or Deprecated (with a link to the superseding ADR).
- **Context** — the forces at play and the problem being decided.
- **Decision** — what we will do.
- **Consequences** — what becomes easier or harder as a result.
- **Alternatives considered** — options that were weighed and why they were not chosen.

Keep ADRs short and durable. Record a decision once it is made; supersede rather than rewrite when it changes.

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-monorepo-and-runtime-boundaries.md) | Monorepo and runtime boundaries for ClipFetch Watch | Accepted |
