"""Reusable catalog filtering and serialization for offline library commands."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from clipfetch.catalog import Catalog, CatalogError, CatalogRecord

_MULTIPLIERS = {
    "": Decimal(1),
    "k": Decimal(1_000),
    "m": Decimal(1_000_000),
    "b": Decimal(1_000_000_000),
}
_MAX_INTEGER = 9_223_372_036_854_775_807


@dataclass(frozen=True)
class ClipFilter:
    """Typed compound filter shared by list, search, and future collections."""

    min_likes: int | None = None
    max_likes: int | None = None
    min_views: int | None = None
    max_views: int | None = None
    authors: tuple[str, ...] = ()
    hashtags: tuple[str, ...] = ()
    platforms: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    downloaded_after: date | None = None
    downloaded_before: date | None = None


@dataclass(frozen=True)
class QueryResult:
    clips: tuple[CatalogRecord, ...]
    matched: int
    excluded: int
    unknown_required_metadata: int


@dataclass(frozen=True)
class FilterDecision:
    matches: bool
    unknown_required_metadata: bool
    rejected_by: tuple[str, ...] = ()


def parse_magnitude(value: str) -> int:
    """Parse non-negative integers with case-insensitive decimal k/m/b suffixes."""
    normalized = value.strip().casefold()
    suffix = normalized[-1:] if normalized[-1:] in _MULTIPLIERS else ""
    number_text = normalized[:-1] if suffix else normalized
    try:
        number = Decimal(number_text)
    except InvalidOperation as err:
        raise ValueError(f"invalid number: {value!r}") from err
    result = number * _MULTIPLIERS[suffix]
    if not number.is_finite() or result < 0:
        raise ValueError("number must be finite and non-negative")
    if result != result.to_integral_value():
        raise ValueError("number must resolve to a whole value")
    if result > _MAX_INTEGER:
        raise ValueError("number is too large")
    return int(result)


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value.strip())
    except ValueError as err:
        raise ValueError(f"invalid date {value!r}; expected YYYY-MM-DD") from err


def query_library(
    root: Path,
    filters: ClipFilter | None = None,
    *,
    sort: str = "date",
    limit: int | None = None,
    offset: int = 0,
) -> QueryResult:
    """Query a catalog with stable ordering and visible exclusion accounting."""
    filters = filters or ClipFilter()
    if not root.is_dir():
        raise CatalogError(f"library directory does not exist: {root.resolve()}")
    with Catalog.open(root) as catalog:
        records = [_refresh_presence(root, record) for record in catalog.all()]
        # One query for all topic assignments instead of one per record (N+1) — matters at scale.
        assigned_topics = catalog.all_topic_names()
    matched: list[CatalogRecord] = []
    unknown_count = 0
    for record in records:
        is_match, unknown = matches_filter(
            record, filters, assigned_topics.get((record.platform, record.clip_id), ())
        )
        if is_match:
            matched.append(record)
        else:
            unknown_count += int(unknown)
    ordered = _sort_records(matched, sort)
    start = min(offset, len(ordered))
    selected = ordered[start:] if limit is None else ordered[start : start + limit]
    return QueryResult(
        clips=tuple(selected),
        matched=len(matched),
        excluded=len(records) - len(matched),
        unknown_required_metadata=unknown_count,
    )


def matches_filter(
    record: CatalogRecord,
    filters: ClipFilter,
    assigned_topics: tuple[str, ...] = (),
) -> tuple[bool, bool]:
    """Return ``(matches, excluded_because_required_value_unknown)``."""
    decision = evaluate_filter(record, filters, assigned_topics)
    return decision.matches, decision.unknown_required_metadata


def evaluate_filter(
    record: CatalogRecord,
    filters: ClipFilter,
    assigned_topics: tuple[str, ...] = (),
) -> FilterDecision:
    """Evaluate every dimension so selection summaries can explain rejections."""
    if not record.available:
        return FilterDecision(False, False, ("unavailable",))
    unknown = False
    rejected: list[str] = []

    for name, value, minimum, maximum in (
        ("likes", record.likes, filters.min_likes, filters.max_likes),
        ("views", record.views, filters.min_views, filters.max_views),
    ):
        if minimum is not None or maximum is not None:
            if value is None:
                unknown = True
                rejected.append(name)
                continue
            if minimum is not None and value < minimum:
                rejected.append(name)
            if maximum is not None and value > maximum:
                rejected.append(name)

    if filters.authors:
        if record.author is None:
            unknown = True
            rejected.append("author")
        elif record.author.casefold() not in {author.casefold() for author in filters.authors}:
            rejected.append("author")
    if filters.hashtags:
        wanted = {tag.removeprefix("#").casefold() for tag in filters.hashtags}
        if not wanted.intersection(tag.casefold() for tag in record.hashtags):
            rejected.append("hashtag")
    if filters.platforms and record.platform.casefold() not in {
        platform.casefold() for platform in filters.platforms
    }:
        rejected.append("platform")
    if filters.topics:
        wanted_topics = {topic.casefold() for topic in filters.topics}
        if not wanted_topics.intersection(topic.casefold() for topic in assigned_topics):
            rejected.append("topic")

    if filters.downloaded_after is not None or filters.downloaded_before is not None:
        downloaded = _record_date(record)
        if downloaded is None:
            unknown = True
            rejected.append("downloaded-date")
        else:
            if filters.downloaded_after and downloaded < filters.downloaded_after:
                rejected.append("downloaded-date")
            if filters.downloaded_before and downloaded > filters.downloaded_before:
                rejected.append("downloaded-date")

    return FilterDecision(not rejected, unknown, tuple(dict.fromkeys(rejected)))


def find_clip(root: Path, clip_id: str) -> CatalogRecord:
    """Find one clip id across platforms, rejecting absent or ambiguous ids."""
    if not root.is_dir():
        raise CatalogError(f"library directory does not exist: {root.resolve()}")
    with Catalog.open(root) as catalog:
        matches = [
            _refresh_presence(root, record) for record in catalog.all() if record.clip_id == clip_id
        ]
    if not matches:
        raise CatalogError(f"clip id not found: {clip_id}")
    if len(matches) > 1:
        platforms = ", ".join(record.platform for record in matches)
        raise CatalogError(f"clip id {clip_id!r} is ambiguous across: {platforms}")
    return matches[0]


def record_to_dict(record: CatalogRecord) -> dict[str, Any]:
    """Stable machine-readable representation of one catalog row."""
    value = asdict(record)
    value["hashtags"] = list(record.hashtags)
    value["id"] = value.pop("clip_id")
    return value


def query_to_dict(result: QueryResult) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "matched": result.matched,
        "excluded": result.excluded,
        "unknown_required_metadata": result.unknown_required_metadata,
        "clips": [record_to_dict(record) for record in result.clips],
    }


def _record_date(record: CatalogRecord) -> date | None:
    try:
        return datetime.fromisoformat(record.downloaded_at.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _refresh_presence(root: Path, record: CatalogRecord) -> CatalogRecord:
    present = (root / record.relative_path).is_file()
    return record if record.available == present else replace(record, available=present)


def _sort_records(records: list[CatalogRecord], sort: str) -> list[CatalogRecord]:
    stable = sorted(records, key=lambda record: (record.platform, record.clip_id))
    if sort == "author":
        return sorted(stable, key=lambda record: (record.author is None, record.author or ""))
    if sort in ("likes", "views"):
        return sorted(
            stable,
            key=lambda record: (
                getattr(record, sort) is not None,
                getattr(record, sort) or 0,
            ),
            reverse=True,
        )
    if sort == "date":
        return sorted(stable, key=lambda record: record.downloaded_at, reverse=True)
    raise ValueError(f"unknown sort: {sort}")
