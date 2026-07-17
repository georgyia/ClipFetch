# Label taxonomy

ClipFetch keeps a small, consistent label set. An issue usually carries one **kind** label, optionally a
**platform** or **scope** label, and any relevant **status** labels.

## Kind — what sort of work

| Label | Color | Meaning |
|---|---|---|
| `bug` | `#d73a4a` | Something isn't working. |
| `enhancement` | `#a2eeef` | New feature or request. |
| `documentation` | `#0075ca` | Documentation improvements or additions. |
| `tech-debt` | `#c5def5` | Cleanup, refactors, internal quality. |
| `ci` | `#bfd4f2` | CI, tooling, packaging. |
| `research` | `#d4c5f9` | Needs investigation / spike. |

## Scope & platform

| Label | Color | Meaning |
|---|---|---|
| `clipfetch-watch` | `#5319e7` | ClipFetch Watch — the local-first streaming interface (API, worker, frontend). Backlog in [docs/ROADMAP.md](../docs/ROADMAP.md). |
| `platform:instagram` | `#e4405f` | Instagram-specific features and fixes. |
| `platform:tiktok` | `#010101` | TikTok download support. |
| `platform:youtube-shorts` | `#ff0000` | YouTube Shorts download support. |

## Status

| Label | Color | Meaning |
|---|---|---|
| `blocked` | `#b60205` | Blocked by an external constraint. |
| `good first issue` | `#7057ff` | Good for newcomers. |
| `help wanted` | `#008672` | Extra attention is welcome. |
| `question` | `#d876e3` | Further information is requested. |
| `duplicate` | `#cfd3d7` | Already tracked elsewhere. |
| `invalid` | `#e4e669` | Doesn't seem right. |
| `wontfix` | `#ffffff` | Will not be worked on. |

## Milestones

ClipFetch Watch work is grouped under the **ClipFetch Watch MVP** milestone. The 39 backlog issues
(#30–#68) are filed there; see [docs/ROADMAP.md](../docs/ROADMAP.md) for the phase order.

## Applying labels

Labels are managed on the repository's **Labels** page or via the CLI, e.g.:

```bash
gh label create "clipfetch-watch" --color 5319e7 \
  --description "ClipFetch Watch streaming interface (API, worker, frontend)"
```
