from __future__ import annotations

from pathlib import Path

import pytest

from clipfetch.catalog import Catalog, CatalogRecord, TopicAssignment
from clipfetch.comments import (
    MAX_COMMENT_CHARACTERS,
    MAX_PAGES_PER_CLIP,
    AuthenticationCheckpoint,
    BackendFailure,
    ClipDeleted,
    ClipUnavailable,
    CommentItem,
    CommentPage,
    CommentsDisabled,
    InstagramCommentBackend,
    RateLimited,
    RequestLimiter,
    enrich_comments,
    purge_comments,
    select_comment_records,
)
from clipfetch.library import ClipFilter
from clipfetch.semantic import semantic_document, semantic_index
from clipfetch.topics import TopicConfig, TopicDefinition, save_topics, tag_clip


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


class FakeBackend:
    def __init__(self, clock: FakeClock | None = None, interrupt_at: int | None = None) -> None:
        self.clock = clock
        self.interrupt_at = interrupt_at
        self.calls = 0
        self.request_times: list[float] = []

    def _called(self) -> None:
        self.calls += 1
        if self.clock:
            self.request_times.append(self.clock())
        if self.calls == self.interrupt_at:
            raise KeyboardInterrupt

    def resolve_media_id(self, record: CatalogRecord) -> str:
        self._called()
        outcomes = {
            "DISABLED": CommentsDisabled("disabled"),
            "DELETED": ClipDeleted("deleted"),
            "UNAVAILABLE": ClipUnavailable("unavailable"),
            "AUTH": AuthenticationCheckpoint("checkpoint"),
            "RATE": RateLimited("429"),
            "FAIL": BackendFailure("backend failed"),
        }
        if record.clip_id in outcomes:
            raise outcomes[record.clip_id]
        return "media-" + record.clip_id

    def fetch_page(self, media_id: str, cursor: str | None, limit: int) -> CommentPage:
        self._called()
        if media_id == "media-EMPTY":
            return CommentPage(())
        if cursor is None:
            return CommentPage(
                (
                    CommentItem("1", "  hello\nworld "),
                    CommentItem("duplicate-text", "hello world"),
                    CommentItem("empty", "   "),
                ),
                "next",
            )
        return CommentPage(
            (CommentItem("1", "changed duplicate id"), CommentItem("2", "second comment"))
        )


class FakeEmbedder:
    model_id = "fake/embed"
    revision = "v1"

    def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


def _record(
    ident: str,
    *,
    platform: str = "instagram",
    likes: int = 10,
    caption: str | None = None,
) -> CatalogRecord:
    noun = "reel" if platform == "instagram" else "tiktok"
    return CatalogRecord(
        platform=platform,
        clip_id=ident,
        relative_path=f"{noun}_001_{ident}.mp4",
        file_size=5,
        file_mtime_ns=1,
        downloaded_at="2026-01-01T00:00:00+00:00",
        source_url=f"https://www.instagram.com/reel/{ident}/",
        author="author",
        caption=caption,
        likes=likes,
        metadata_state="catalog",
    )


def _library(root: Path, *records: CatalogRecord) -> None:
    with Catalog.open(root) as catalog:
        for record in records:
            catalog.upsert(record)
            (root / record.relative_path).write_bytes(record.clip_id.encode())


def _limiter(clock: FakeClock) -> RequestLimiter:
    return RequestLimiter(clock=clock, sleep=clock.sleep)


def test_normalization_deduplication_pagination_and_one_second_limit(tmp_path):
    _library(tmp_path, _record("A"))
    records = select_comment_records(tmp_path)
    clock = FakeClock()
    backend = FakeBackend(clock)
    report = enrich_comments(
        tmp_path,
        backend,
        records,
        max_comments=2,
        limiter=_limiter(clock),
    )
    assert report.completed == 1
    assert backend.request_times == [0.0, 1.0, 2.0]
    assert clock.sleeps == [1.0, 1.0]
    with Catalog.open(tmp_path) as catalog:
        comments = catalog.comments_for("instagram", "A")
        assert [(item.comment_id, item.text) for item in comments] == [
            ("1", "hello world"),
            ("2", "second comment"),
        ]
        record = catalog.get("instagram", "A")
        assert record.comment_text == "hello world\nsecond comment"
        assert record.comment_status == "complete"
        columns = {
            row[1] for row in catalog._connection.execute("PRAGMA table_info(clip_comments)")
        }
        assert columns == {"platform", "clip_id", "comment_id", "text", "retrieved_at"}


def test_filters_and_platform_are_applied_to_local_files(tmp_path):
    _library(
        tmp_path,
        _record("LOW", likes=1),
        _record("HIGH", likes=100),
        _record("TIK", platform="tiktok", likes=100),
    )
    selected = select_comment_records(tmp_path, ClipFilter(min_likes=50))
    assert [record.clip_id for record in selected] == ["HIGH"]
    (tmp_path / "reel_001_HIGH.mp4").unlink()
    assert select_comment_records(tmp_path, ClipFilter(min_likes=50)) == ()


def test_independent_terminal_and_retryable_outcomes(tmp_path):
    records = tuple(
        _record(ident)
        for ident in ("DISABLED", "DELETED", "UNAVAILABLE", "AUTH", "RATE", "FAIL", "EMPTY")
    )
    _library(tmp_path, *records)
    clock = FakeClock()
    report = enrich_comments(
        tmp_path,
        FakeBackend(clock),
        select_comment_records(tmp_path),
        limiter=_limiter(clock),
    )
    assert (
        report.disabled,
        report.deleted,
        report.unavailable,
        report.authentication_checkpoint,
        report.rate_limited,
        report.failed,
        report.empty,
    ) == (1, 1, 1, 1, 1, 1, 1)
    with Catalog.open(tmp_path) as catalog:
        assert catalog.get("instagram", "DISABLED").comment_status == "disabled"
        assert catalog.get("instagram", "AUTH").comment_status == "authentication-checkpoint"
        assert catalog.get("instagram", "RATE").comment_status == "rate-limited"
        assert catalog.get("instagram", "FAIL").comment_status == "failed"


def test_incremental_commit_interrupt_and_resume(tmp_path):
    _library(tmp_path, _record("A"), _record("B"))
    selected = select_comment_records(tmp_path)
    clock = FakeClock()
    with pytest.raises(KeyboardInterrupt):
        enrich_comments(
            tmp_path,
            FakeBackend(clock, interrupt_at=4),
            selected,
            limiter=_limiter(clock),
        )
    with Catalog.open(tmp_path) as catalog:
        assert catalog.get("instagram", "A").comment_status == "complete"
        assert catalog.get("instagram", "B").comment_status is None
    resumed = enrich_comments(
        tmp_path,
        FakeBackend(FakeClock()),
        selected,
        limiter=_limiter(FakeClock()),
    )
    assert resumed.skipped == 1 and resumed.completed == 1


def test_comment_semantics_selective_invalidation_manual_preservation_and_purge(tmp_path):
    _library(
        tmp_path,
        _record("A", caption="startup"),
        _record("B", caption="neighbor"),
    )
    save_topics(
        tmp_path,
        TopicConfig(0.5, (TopicDefinition("business", "companies", ("founder",)),)),
    )
    tag_clip(tmp_path, "A", "business")
    assert semantic_index(tmp_path, FakeEmbedder()).indexed == 2
    with Catalog.open(tmp_path) as catalog:
        for ident in ("A", "B"):
            catalog.replace_model_topics(
                "instagram",
                ident,
                [
                    TopicAssignment(
                        "instagram",
                        ident,
                        "uncategorized",
                        0.0,
                        "model",
                        "fake/embed",
                        "v1",
                        "definition",
                        "input",
                        0.5,
                        "2026-01-01T00:00:00+00:00",
                    )
                ],
            )
    clock = FakeClock()
    enrich_comments(
        tmp_path,
        FakeBackend(clock),
        [select_comment_records(tmp_path)[0]],
        limiter=_limiter(clock),
    )
    with Catalog.open(tmp_path) as catalog:
        a = catalog.get("instagram", "A")
        assert semantic_document(a) == (
            "caption: startup\ncomments: hello world\nsecond comment"
        )
        assert catalog.get_embedding("instagram", "A", "fake/embed", "v1") is None
        assert catalog.topic_names("instagram", "A") == ("business",)
        assert catalog.get_embedding("instagram", "B", "fake/embed", "v1") is not None
        assert catalog.topic_names("instagram", "B") == ("uncategorized",)
    assert semantic_index(tmp_path, FakeEmbedder()).indexed == 1
    assert purge_comments(tmp_path) == 1
    with Catalog.open(tmp_path) as catalog:
        assert catalog.comments_for("instagram", "A") == []
        assert catalog.get("instagram", "A").comment_text is None
        assert catalog.topic_names("instagram", "A") == ("business",)
        assert catalog.get_embedding("instagram", "A", "fake/embed", "v1") is None
    rebuilt = semantic_index(tmp_path, FakeEmbedder())
    assert rebuilt.indexed == 1 and rebuilt.unchanged == 1


def test_catalog_reindex_preserves_comments(tmp_path):
    from clipfetch.catalog import index_library

    _library(tmp_path, _record("A"))
    clock = FakeClock()
    enrich_comments(
        tmp_path,
        FakeBackend(clock),
        select_comment_records(tmp_path),
        limiter=_limiter(clock),
    )
    assert index_library(tmp_path).updated == 1
    assert index_library(tmp_path).unchanged == 1
    with Catalog.open(tmp_path) as catalog:
        assert catalog.get("instagram", "A").comment_text == (
            "hello world\nsecond comment"
        )


def test_sampling_is_bounded_by_pages_and_retained_characters(tmp_path):
    class EndlessBackend(FakeBackend):
        def fetch_page(self, media_id, cursor, limit):
            self._called()
            number = self.calls
            return CommentPage(
                (CommentItem(str(number), "x" * 2_000),),
                f"cursor-{number}",
            )

    _library(tmp_path, _record("A"))
    clock = FakeClock()
    backend = EndlessBackend(clock)
    enrich_comments(
        tmp_path,
        backend,
        select_comment_records(tmp_path),
        max_comments=100,
        limiter=_limiter(clock),
    )
    assert backend.calls == MAX_PAGES_PER_CLIP + 1  # media lookup plus bounded pages
    with Catalog.open(tmp_path) as catalog:
        assert len(catalog.get("instagram", "A").comment_text) <= MAX_COMMENT_CHARACTERS


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status
        self.disposed = False

    def json(self):
        return self.payload

    def dispose(self):
        self.disposed = True


class FakeRequest:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def test_playwright_adapter_discards_profile_fields_and_maps_http_outcomes():
    responses = [
        FakeResponse({"items": [{"pk": "99", "user": {"username": "private"}}]}),
        FakeResponse(
            {
                "comments": [
                    "malformed",
                    {"pk": "deleted", "text": "gone", "is_deleted": True},
                    {
                        "pk": "1",
                        "text": "useful context",
                        "user": {
                            "username": "private",
                            "profile_pic_url": "https://private.invalid/avatar",
                        },
                        "like_count": 50,
                    }
                ]
            }
        ),
    ]
    request = FakeRequest(responses)
    backend = InstagramCommentBackend(type("Context", (), {"request": request})())
    assert backend.resolve_media_id(_record("A")) == "99"
    page = backend.fetch_page("99", None, 20)
    assert page.comments == (CommentItem("1", "useful context"),)
    assert all(response.disposed for response in responses)
    assert "X-IG-App-ID" in request.calls[0][1]["headers"]

    limited = InstagramCommentBackend(
        type("Context", (), {"request": FakeRequest([FakeResponse({}, 429)])})()
    )
    with pytest.raises(RateLimited):
        limited.resolve_media_id(_record("A"))
