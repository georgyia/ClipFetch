"""Deterministic recommendation and diversity ranking.

Given a seed clip and a candidate pool, produce a stable "more like this" ordering from explainable,
rule-based signals — no learned model, no randomness. Signals: topical relatedness (Jaccard of
topics + hashtags), normalized popularity (log-scaled likes/views), and freshness (recency rank).
Diversity constraints then cap how many clips one creator contributes and drop near-duplicates, so a
single prolific creator or a re-post can't dominate.

Identical inputs always yield identical output: every sort has a full tie-breaker chain ending in
the clip id. Operates only on :class:`~clipfetch.contracts.ClipSummary` values.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path

from clipfetch.catalog import CatalogError
from clipfetch.contracts import ClipSummary
from clipfetch.library import ClipFilter

# Signal weights. Relatedness dominates; popularity and freshness only break near-ties.
_W_RELATED = 0.6
_W_POPULARITY = 0.25
_W_FRESHNESS = 0.15

DEFAULT_LIMIT = 12
DEFAULT_MAX_PER_CREATOR = 2
_CANDIDATE_CAP = 200


def _tag_set(clip: ClipSummary) -> set[str]:
    return {t.lower() for t in clip.topics} | {h.lower() for h in clip.hashtags}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def _popularity(clip: ClipSummary) -> float:
    return math.log1p(max(0, clip.likes or 0)) + math.log1p(max(0, clip.views or 0))


def _min_max(values: Sequence[float]) -> list[float]:
    if not values:
        return []
    low, high = min(values), max(values)
    if high <= low:
        return [0.5 for _ in values]  # all equal: neutral, still deterministic
    span = high - low
    return [(value - low) / span for value in values]


def rank_related(
    seed: ClipSummary,
    candidates: Sequence[ClipSummary],
    *,
    limit: int = DEFAULT_LIMIT,
    max_per_creator: int = DEFAULT_MAX_PER_CREATOR,
) -> list[ClipSummary]:
    """Rank candidates by relatedness to ``seed`` under diversity/duplicate constraints."""
    pool: list[ClipSummary] = []
    seen_ids = {seed.id}
    for clip in candidates:
        if clip.id in seen_ids or not clip.available:
            continue
        seen_ids.add(clip.id)
        pool.append(clip)
    if not pool:
        return []

    seed_tags = _tag_set(seed)
    popularity = _min_max([_popularity(clip) for clip in pool])
    # Freshness: rank by downloaded_at (ISO strings sort chronologically), newest = 1.0.
    order = sorted(
        range(len(pool)), key=lambda i: (pool[i].downloaded_at, pool[i].id), reverse=True
    )
    freshness = [0.0] * len(pool)
    for rank, index in enumerate(order):
        freshness[index] = 1.0 - (rank / max(1, len(pool) - 1)) if len(pool) > 1 else 1.0

    scored: list[tuple[float, str, str, ClipSummary]] = []
    for index, clip in enumerate(pool):
        score = (
            _W_RELATED * _jaccard(seed_tags, _tag_set(clip))
            + _W_POPULARITY * popularity[index]
            + _W_FRESHNESS * freshness[index]
        )
        # Sort key: score desc, then newest, then id — a full deterministic chain.
        scored.append((score, clip.downloaded_at, clip.id, clip))
    scored.sort(key=lambda item: (-item[0], _reverse_str(item[1]), item[2]))

    result: list[ClipSummary] = []
    per_creator: dict[str | None, int] = {}
    seen_signatures: set[tuple[str | None, str | None]] = set()
    for _score, _date, _id, clip in scored:
        if per_creator.get(clip.author, 0) >= max_per_creator:
            continue
        signature = (clip.author, clip.caption)
        if clip.caption and signature in seen_signatures:  # near-duplicate re-post
            continue
        result.append(clip)
        per_creator[clip.author] = per_creator.get(clip.author, 0) + 1
        seen_signatures.add(signature)
        if len(result) >= limit:
            break
    return result


def _reverse_str(value: str) -> tuple[int, ...]:
    """A sort key that orders strings descending while keeping the sort stable and deterministic."""
    return tuple(-ord(ch) for ch in value)


def _gather_candidates(root: Path, seed: ClipSummary) -> list[ClipSummary]:
    from clipfetch.services import catalog_service

    pool: dict[str, ClipSummary] = {}
    for topic in seed.topics:
        try:
            page = catalog_service.list_clips(
                root, ClipFilter(topics=(topic,)), sort="likes", limit=50
            )
        except CatalogError:
            continue
        for item in page.items:
            pool.setdefault(item.id, item)
    # Augment with the most popular recent clips so recommendations exist even without topics.
    try:
        popular = catalog_service.list_clips(root, sort="likes", limit=50)
        for item in popular.items:
            pool.setdefault(item.id, item)
    except CatalogError:
        pass
    pool.pop(seed.id, None)
    return list(pool.values())[:_CANDIDATE_CAP]


def recommend_related(root: Path, clip_id: str, *, limit: int = DEFAULT_LIMIT) -> list[ClipSummary]:
    """Gather candidates for ``clip_id`` and return a ranked, diverse "more like this" list."""
    from clipfetch.services import catalog_service

    seed = catalog_service.get_clip(root, clip_id).summary
    return rank_related(seed, _gather_candidates(root, seed), limit=limit)
