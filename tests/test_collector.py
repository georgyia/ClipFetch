from clipfetch.collector import ClipCollector, SelectionStats
from clipfetch.library import FilterDecision
from clipfetch.model import Quality
from clipfetch.platforms.instagram import Instagram
from tests.test_instagram import FEED_PAYLOAD

instagram = Instagram()


class FakeResponse:
    url = "https://www.instagram.com/api/v1/clips/home/"
    status = 200
    headers = {"content-type": "application/json; charset=utf-8"}

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def _collector(limit, on_clip=lambda c: None, active=None, already_have=None):
    return ClipCollector(
        instagram, Quality.HIGH, limit, on_clip, active=active, already_have=already_have
    )


def test_collector_dedupes_and_respects_limit():
    seen = []
    collector = _collector(3, on_clip=seen.append)
    collector.handle_response(FakeResponse(FEED_PAYLOAD))
    collector.handle_response(FakeResponse(FEED_PAYLOAD))  # duplicate batch
    assert [c.ident for c in collector.clips] == ["ABC123", "DEF456"]
    assert not collector.full

    more = {
        "items": [
            {"media": {"code": "GHI789", "video_versions": [{"url": "https://cdn.test/g.mp4"}]}},
            {"media": {"code": "JKL012", "video_versions": [{"url": "https://cdn.test/j.mp4"}]}},
        ]
    }
    collector.handle_response(FakeResponse(more))
    assert collector.full
    assert len(collector.clips) == 3  # limit enforced mid-batch
    assert seen == collector.clips  # every clip reported exactly once


def test_collector_skips_already_downloaded():
    collector = _collector(5, already_have={"ABC123"})
    collector.handle_response(FakeResponse(FEED_PAYLOAD))
    assert [c.ident for c in collector.clips] == ["DEF456"]


def test_collector_ignores_responses_while_inactive():
    on_reels_page = {"value": False}
    collector = _collector(5, active=lambda: on_reels_page["value"])

    collector.handle_response(FakeResponse(FEED_PAYLOAD))  # still on home feed
    assert collector.clips == []

    on_reels_page["value"] = True
    collector.handle_response(FakeResponse(FEED_PAYLOAD))
    assert [c.ident for c in collector.clips] == ["ABC123", "DEF456"]


def test_collector_ignores_non_json_and_foreign_responses():
    collector = _collector(5)

    html = FakeResponse(FEED_PAYLOAD)
    html.headers = {"content-type": "text/html"}
    collector.handle_response(html)

    foreign = FakeResponse(FEED_PAYLOAD)
    foreign.url = "https://tracking.example.com/api"
    collector.handle_response(foreign)

    broken = FakeResponse(FEED_PAYLOAD)
    broken.json = lambda: (_ for _ in ()).throw(ValueError("not json"))
    collector.handle_response(broken)

    assert collector.clips == []


def test_selection_counts_unique_scanned_separately_from_accepted():
    submitted = []
    stats = SelectionStats()

    def selector(clip):
        if clip.likes is None:
            return FilterDecision(False, True, ("likes",))
        return FilterDecision(clip.likes >= 4000, False, (() if clip.likes >= 4000 else ("likes",)))

    collector = ClipCollector(
        instagram,
        Quality.HIGH,
        2,
        submitted.append,
        scan_limit=3,
        selector=selector,
        stats=stats,
    )
    collector.handle_response(FakeResponse(FEED_PAYLOAD))
    collector.handle_response(FakeResponse(FEED_PAYLOAD))  # duplicates use no budget
    more = {
        "media": {
            "code": "THIRD",
            "like_count": 5000,
            "video_versions": [{"url": "https://cdn.test/third.mp4"}],
        }
    }
    collector.handle_response(FakeResponse(more))
    assert [clip.ident for clip in submitted] == ["ABC123", "THIRD"]
    assert (stats.scanned, stats.accepted, stats.rejected) == (3, 2, 1)
    assert stats.unknown_required_metadata == 1
    assert stats.rejected_by == {"likes": 1}


def test_exact_scan_limit_stops_sparse_selection_and_never_submits_rejected():
    submitted = []
    stats = SelectionStats()
    collector = ClipCollector(
        instagram,
        Quality.HIGH,
        5,
        submitted.append,
        scan_limit=2,
        selector=lambda clip: FilterDecision(False, False, ("topic",)),
        stats=stats,
    )
    collector.handle_response(FakeResponse(FEED_PAYLOAD))
    assert collector.full and stats.stopped_by_scan_limit
    assert stats.scanned == 2 and stats.rejected == 2
    assert submitted == []
