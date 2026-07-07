from clipfetch.collector import ClipCollector
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

    more = {"items": [
        {"media": {"code": "GHI789", "video_versions": [{"url": "https://cdn.test/g.mp4"}]}},
        {"media": {"code": "JKL012", "video_versions": [{"url": "https://cdn.test/j.mp4"}]}},
    ]}
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
