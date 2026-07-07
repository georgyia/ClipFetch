from clipfetch.reels import Reel, ReelCollector, find_reels

# Trimmed-down shape of Instagram's clips feed API responses.
FEED_PAYLOAD = {
    "items": [
        {
            "media": {
                "code": "ABC123",
                "video_versions": [
                    {"url": "https://cdn.test/abc_low.mp4", "width": 480},
                    {"url": "https://cdn.test/abc_hi.mp4", "width": 1080},
                ],
            }
        },
        {
            "media": {
                "code": "PHOTO1",  # image post: no video_versions
                "image_versions2": {"candidates": [{"url": "https://cdn.test/p.jpg"}]},
            }
        },
        {
            "media": {
                "code": "DEF456",
                "video_versions": [{"url": "https://cdn.test/def.mp4", "width": 720}],
            }
        },
    ],
    "paging_info": {"more_available": True},
}


class FakeResponse:
    url = "https://www.instagram.com/api/v1/clips/home/"
    status = 200
    headers = {"content-type": "application/json; charset=utf-8"}

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_find_reels_picks_best_quality_and_skips_photos():
    reels = list(find_reels(FEED_PAYLOAD))
    assert reels == [
        Reel("ABC123", "https://cdn.test/abc_hi.mp4"),
        Reel("DEF456", "https://cdn.test/def.mp4"),
    ]


def test_find_reels_handles_junk_payloads():
    assert list(find_reels(None)) == []
    assert list(find_reels({"status": "ok"})) == []
    assert list(find_reels([1, "x", {"code": "NOVIDEO"}])) == []
    assert list(find_reels({"media": {"code": "X", "video_versions": []}})) == []


def test_collector_dedupes_and_respects_limit():
    seen = []
    collector = ReelCollector(limit=3, on_reel=seen.append)
    collector.handle_response(FakeResponse(FEED_PAYLOAD))
    collector.handle_response(FakeResponse(FEED_PAYLOAD))  # duplicate batch
    assert [r.shortcode for r in collector.reels] == ["ABC123", "DEF456"]
    assert not collector.full

    more = {"items": [{"media": {"code": "GHI789",
                                 "video_versions": [{"url": "https://cdn.test/g.mp4"}]}},
                      {"media": {"code": "JKL012",
                                 "video_versions": [{"url": "https://cdn.test/j.mp4"}]}}]}
    collector.handle_response(FakeResponse(more))
    assert collector.full
    assert len(collector.reels) == 3  # limit enforced mid-batch
    assert seen == collector.reels  # every reel reported exactly once


def test_collector_ignores_non_json_and_foreign_responses():
    collector = ReelCollector(limit=5, on_reel=lambda r: None)

    html = FakeResponse(FEED_PAYLOAD)
    html.headers = {"content-type": "text/html"}
    collector.handle_response(html)

    foreign = FakeResponse(FEED_PAYLOAD)
    foreign.url = "https://tracking.example.com/api"
    collector.handle_response(foreign)

    broken = FakeResponse(FEED_PAYLOAD)
    broken.json = lambda: (_ for _ in ()).throw(ValueError("not json"))
    collector.handle_response(broken)

    assert collector.reels == []
