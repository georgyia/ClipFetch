# Support

Thanks for using ClipFetch. Here's how to get help.

## Before you ask

- Read the [README](README.md) — the Usage and Deeper capabilities sections cover most commands and their
  behavior.
- Run `clipfetch --help` (and `clipfetch library --help`) for the full, current option list.
- Search [existing issues](https://github.com/georgyia/ClipFetch/issues?q=is%3Aissue) — your question may already
  be answered.

## Where to go

| I want to… | Go to |
|---|---|
| Report a bug | [Open a bug report](https://github.com/georgyia/ClipFetch/issues/new/choose) |
| Request a feature | [Open a feature request](https://github.com/georgyia/ClipFetch/issues/new/choose) |
| Ask a usage question | [GitHub Discussions](https://github.com/georgyia/ClipFetch/discussions) if enabled, otherwise open a question issue |
| Report a security issue | Follow [SECURITY.md](SECURITY.md) — **do not** open a public issue |
| Understand the streaming roadmap | [docs/ROADMAP.md](docs/ROADMAP.md) and the [full plan](docs/clipfetch-watch-plan.md) |

## Helpful details to include

When reporting a bug, the following makes it much faster to help:

- ClipFetch version, OS, and Python version.
- The exact command you ran and the output (redact anything private).
- Which platform (Instagram / TikTok) and whether it's your feed or a specific account.
- Whether you're using any optional extras (`semantic`, `transcribe`, `duplicates`, `cookies`).

## Common gotchas

- **"Please sign in"** — the first run opens a browser so you can sign in once; the session is stored in
  `~/.clipfetch/profile`. See the README Quickstart.
- **TikTok downloads fail** — this is expected; TikTok is experimental. Use `--dry-run` to list URLs.
- **YouTube Shorts** — not supported by design (see the README Platform support table).
- **Semantic search import errors** — install the extra: `pip install "clipfetch[semantic]"` (Python 3.10+).

For anything else, open an issue — friendly questions are welcome.
