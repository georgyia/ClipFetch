"""Typed download outcome model.

The download *flow* (open a browser session, collect from the feed, run the download pool) stays in
the caller: the CLI drives it with a Console, and the future web worker will drive it with a job
reporter. What both need — and what was previously tangled inline in ``clipfetch.cli._run`` — is a
typed, presentation-free summary of what happened and a single place that decides what an empty
result *means*. That is this module.

It imports nothing from argparse, FastAPI, or the UI, and reads raw download results structurally
(via :class:`RawResult`) so it never pulls in the browser stack. Nothing here carries device paths,
cookies, or URLs; a clip is identified only by its ident.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol


class RawClip(Protocol):
    @property
    def ident(self) -> str: ...


class RawResult(Protocol):
    """The subset of a downloader result the summary needs. Matches DownloadPool/browser results.

    Members are read-only so a frozen dataclass with a computed ``ok`` property satisfies it.
    """

    @property
    def ok(self) -> bool: ...

    @property
    def size(self) -> int: ...

    @property
    def error(self) -> str | None: ...

    @property
    def catalog_error(self) -> str | None: ...

    @property
    def clip(self) -> RawClip: ...


@dataclass(frozen=True)
class ClipResult:
    """Presentation-free per-clip result."""

    ident: str
    ok: bool
    size: int
    error: str | None
    catalog_warning: str | None


@dataclass(frozen=True)
class EmptyReason:
    """Why a run produced no downloads. ``kind`` is stable for callers to map to their own domain.

    - ``"no_matches"``: the feed yielded candidates but none passed the requested filters. Not an
      error — the caller reports it and stops.
    - ``"blocked"``: an experimental platform blocked the downloads (anti-bot).
    - ``"empty"``: nothing downloaded for another reason.
    """

    kind: str
    message: str | None


@dataclass(frozen=True)
class DownloadOutcome:
    """Typed summary of a download run."""

    requested: int
    found: int
    accepted: int
    results: tuple[ClipResult, ...]

    @property
    def downloaded(self) -> tuple[ClipResult, ...]:
        return tuple(result for result in self.results if result.ok)

    @property
    def downloaded_count(self) -> int:
        return sum(1 for result in self.results if result.ok)

    @property
    def failed_count(self) -> int:
        return sum(1 for result in self.results if not result.ok)

    @property
    def total_bytes(self) -> int:
        return sum(result.size for result in self.results if result.ok)

    def empty_reason(
        self, *, experimental: bool, has_filters: bool, platform_label: str, noun: str
    ) -> EmptyReason | None:
        """Classify an empty run, or ``None`` when at least one clip downloaded."""
        if self.downloaded_count > 0:
            return None
        if self.accepted == 0 and has_filters:
            return EmptyReason("no_matches", None)
        if experimental:
            return EmptyReason(
                "blocked",
                f"No {noun}s could be downloaded — {platform_label} blocked the requests "
                "(anti-bot). Extraction still works: try --dry-run to get the video URLs.",
            )
        return EmptyReason("empty", f"No {noun}s could be downloaded.")


def summarize(
    results: Iterable[RawResult], *, requested: int, found: int, accepted: int
) -> DownloadOutcome:
    """Build a :class:`DownloadOutcome` from an iterable of raw downloader results."""
    clips = tuple(
        ClipResult(
            ident=result.clip.ident,
            ok=result.ok,
            size=result.size,
            error=result.error,
            catalog_warning=result.catalog_error,
        )
        for result in results
    )
    return DownloadOutcome(requested=requested, found=found, accepted=accepted, results=clips)
