from __future__ import annotations

from clipfetch.contracts import ClipSummary
from clipfetch.services import ranking_service
from clipfetch.services.ranking_service import rank_related


def _clip(clip_id, *, author="a", topics=(), hashtags=(), likes=0, views=0, downloaded="2026-01-01",
          caption=None, available=True):
    return ClipSummary(
        id=clip_id,
        platform="instagram",
        author=author,
        caption=caption,
        likes=likes,
        views=views,
        comments_count=None,
        duration_seconds=None,
        published_at=None,
        downloaded_at=downloaded,
        available=available,
        metadata_state="complete",
        hashtags=tuple(hashtags),
        topics=tuple(topics),
        source_url=None,
    )


def test_relatedness_dominates_ordering():
    seed = _clip("seed", topics=("cooking",), hashtags=("pasta",))
    related = _clip("related", author="b", topics=("cooking",), hashtags=("pasta",), likes=1)
    popular_unrelated = _clip("popular", author="c", topics=("fitness",), likes=1_000_000)
    ranked = rank_related(seed, [popular_unrelated, related])
    assert ranked[0].id == "related"  # shared tags beat raw popularity


def test_is_deterministic():
    seed = _clip("seed", topics=("t",))
    pool = [_clip(f"c{i}", author=f"a{i}", topics=("t",), likes=i) for i in range(10)]
    first = [clip.id for clip in rank_related(seed, pool)]
    second = [clip.id for clip in rank_related(seed, list(reversed(pool)))]
    assert first == second


def test_creator_diversity_is_capped():
    seed = _clip("seed", topics=("t",))
    pool = [_clip(f"c{i}", author="prolific", topics=("t",), likes=i) for i in range(5)]
    pool.append(_clip("other", author="someone", topics=("t",), likes=1))
    ranked = rank_related(seed, pool, max_per_creator=2)
    from_prolific = [clip for clip in ranked if clip.author == "prolific"]
    assert len(from_prolific) <= 2


def test_seed_and_unavailable_and_duplicates_excluded():
    seed = _clip("seed", topics=("t",), caption="hi")
    pool = [
        seed,  # the seed itself
        _clip("gone", topics=("t",), available=False),
        _clip("dup1", author="x", topics=("t",), caption="same"),
        _clip("dup2", author="x", topics=("t",), caption="same"),  # near-duplicate re-post
    ]
    ids = [clip.id for clip in rank_related(seed, pool)]
    assert "seed" not in ids
    assert "gone" not in ids
    assert ids.count("dup1") + ids.count("dup2") == 1


def test_empty_pool_returns_empty():
    assert rank_related(_clip("seed"), []) == []


def test_all_equal_signals_stay_complete_and_deterministic():
    seed = _clip("seed", topics=("t",))
    pool = [_clip(f"c{i}", author=f"a{i}", topics=("t",), likes=5) for i in range(4)]
    a = [clip.id for clip in rank_related(seed, pool)]
    b = [clip.id for clip in rank_related(seed, list(reversed(pool)))]
    assert a == b
    assert set(a) == {"c0", "c1", "c2", "c3"}


def test_module_constants_are_sane():
    assert ranking_service.DEFAULT_MAX_PER_CREATOR >= 1
