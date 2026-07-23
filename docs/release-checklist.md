# Release checklist

A repeatable, mostly-manual checklist for cutting a ClipFetch release (CLI + the ClipFetch Watch
preview). ClipFetch is single-package: the Python distribution ships the built web bundle as package
data, so "release" means one version, one tag, one artifact.

Keep this list honest: a box is checked only when the step actually passed, and anything skipped is
noted in the release notes rather than silently omitted.

## 1. Pre-flight

- [ ] `main` is green: the CI **CI** and **Web CI** workflows pass, including the `web-smoke` job.
- [ ] Working tree is clean and up to date with `origin/main`.
- [ ] Milestone issues for this release are closed (or explicitly deferred with a note).
- [ ] Decide the version and confirm it follows semver relative to the last tag.

## 2. Gates (run locally)

Backend:

- [ ] `ruff check .`
- [ ] `mypy`
- [ ] `python -m pytest -q` on the oldest and newest supported Python (3.9 and 3.13).

Frontend:

- [ ] `npm --prefix web ci`
- [ ] `npm --prefix web run typecheck`
- [ ] `npm --prefix web run lint`
- [ ] `npm --prefix web test`
- [ ] `npm --prefix web run build` (writes the bundle into `clipfetch/webui/`).

Optional/opt-in (run when the release touches these subsystems):

- [ ] `pytest -m integration tests/integration` (real Chromium against local fixtures).
- [ ] The semantic / transcription / duplicate integration markers, as relevant.

## 3. Packaged clean-install smoke

Prove the wheel ships the UI bundle and serves it end to end (mirrors the CI `web-smoke` job):

- [ ] With a fresh venv: `npm --prefix web run build` → `pip install ".[web]"` (non-editable).
- [ ] `python scripts/smoke_web.py` passes (SPA at `/`, deep-link fallback, API/health respond).
- [ ] Manually: `clipfetch web`, register + activate a small library, confirm Home rails, the player,
      seek/next/previous, and the Settings support bundle all work.
- [ ] `clipfetch web --demo` processes a queued job to `succeeded` on the Downloads page.
- [ ] Confirm the redacted support bundle contains no paths, library names, captions, or URLs.

## 4. Version bump and metadata

- [ ] Bump `__version__` in `clipfetch/__init__.py` (the single source `pyproject.toml` reads).
- [ ] Update `CHANGELOG`/release notes: user-facing changes, new `clipfetch web` usage, and the
      current Watch **preview** limitations (no live in-app download source yet).
- [ ] Confirm docs are accurate for the release: [watch-user-guide.md](watch-user-guide.md),
      [README](../README.md), and [ROADMAP.md](ROADMAP.md).

## 5. Build and verify the artifact

- [ ] `python -m build` produces an sdist and a wheel.
- [ ] Inspect the wheel: it contains `clipfetch/webui/index.html` and `clipfetch/webui/assets/*`
      (`python -m zipfile -l dist/clipfetch-*.whl | grep webui`).
- [ ] `twine check dist/*` passes.

## 6. Tag and publish

- [ ] Commit the version bump and notes; open/merge the release PR.
- [ ] Tag `vX.Y.Z` on the merge commit and push the tag.
- [ ] Publish per the release workflow; confirm the published artifact matches the local build.
- [ ] Create the GitHub release with notes and known limitations.

## 7. Post-release

- [ ] Fresh-environment install of the published artifact runs `clipfetch --version` and
      `clipfetch web`.
- [ ] Close the milestone; open the next one and roll any deferred items forward.
- [ ] Announce, noting clearly what ships (CLI + Watch preview) versus what is still roadmap.
