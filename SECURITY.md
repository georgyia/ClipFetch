# Security Policy

ClipFetch is a **local-first, single-user** tool. It runs on your machine, stores data on your machine, and does
not expose a network service by default. Even so, it handles authenticated browser sessions, cookies, and
downloaded media, so we take security reports seriously.

## Supported versions

ClipFetch is pre-1.0 and ships from `main`. Security fixes are applied to the latest release and to `main`. Please
verify a report reproduces on the latest version before submitting.

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Report privately to **contact@aiphase.de**. If you can, use
[GitHub's private vulnerability reporting](https://github.com/georgyia/ClipFetch/security/advisories/new) for the
repository.

Please include:

- A description of the issue and its impact.
- Step-by-step reproduction, ideally with a minimal case.
- Affected version, OS, and Python version.
- Any suggested remediation.

We aim to acknowledge reports within a few days and to keep you informed as we investigate and fix. Please give us
reasonable time to release a fix before any public disclosure, and act in good faith — do not access, modify, or
exfiltrate data that is not yours while testing.

## In scope

Because ClipFetch's privacy posture is central to its design, the following are explicitly in scope:

- **Path traversal / arbitrary file access** — any way to read or write files outside a resolved library root
  (this is a hard constraint for the planned media endpoints, too).
- **Secret leakage** — cookies, authentication headers, session tokens, or expiring CDN/media URLs appearing in
  the catalog, metadata sidecars, exports, logs, or diagnostic output.
- **Cookie-handling flaws** — issues in the cross-browser cookie import (`clipfetch/cookies.py`) that could expose
  or mishandle credential material.
- **Untrusted-data handling** — mishandling of captions, comments, creator names, or other source-provided text
  that could lead to injection when rendered or exported.
- **Sandbox/command execution** — any path where crafted source data or filenames could lead to unintended command
  execution.

## Out of scope

- Vulnerabilities in third-party platforms (Instagram, TikTok, YouTube) themselves.
- Rate-limiting or anti-bot behavior of third-party sources.
- Issues that require an already-compromised local machine or physical access.
- The absence of features that are documented as not-yet-implemented (e.g. the ClipFetch Watch web service).

Thank you for helping keep ClipFetch and its users safe.
