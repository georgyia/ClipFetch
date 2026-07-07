from clipfetch.model import Clip, Quality
from clipfetch.platforms.tiktok import TikTok

tiktok = TikTok()

FEED_PAYLOAD = {
    "itemList": [
        {
            "id": "7290000000000000001",
            "desc": "a clip",
            "video": {
                "bitrateInfo": [
                    {"Bitrate": 500000, "PlayAddr": {"UrlList": ["https://cdn.tt/lo.mp4"]}},
                    {"Bitrate": 900000, "PlayAddr": {"UrlList": ["https://cdn.tt/mid.mp4"]}},
                    {"Bitrate": 1500000, "PlayAddr": {"UrlList": ["https://cdn.tt/hi.mp4"]}},
                ],
                "playAddr": "https://cdn.tt/fallback.mp4",
            },
        },
        {
            "id": "7290000000000000002",
            "video": {"playAddr": "https://cdn.tt/only.mp4"},  # no bitrateInfo
        },
        {"id": "notavideo", "author": {"nickname": "x"}},  # no video object
    ]
}


def _clips(payload, quality=Quality.HIGH):
    return list(tiktok.find_clips(payload, quality))


def test_find_clips_extracts_id_and_best_bitrate_with_referer():
    clips = _clips(FEED_PAYLOAD)
    assert clips == [
        Clip("tiktok", "7290000000000000001", "https://cdn.tt/hi.mp4", referer="https://www.tiktok.com/"),
        Clip("tiktok", "7290000000000000002", "https://cdn.tt/only.mp4", referer="https://www.tiktok.com/"),
    ]


def test_quality_selection_over_bitrates():
    assert _clips(FEED_PAYLOAD, Quality.LOW)[0].video_url == "https://cdn.tt/lo.mp4"
    assert _clips(FEED_PAYLOAD, Quality.MEDIUM)[0].video_url == "https://cdn.tt/mid.mp4"


def test_feed_and_target_urls():
    assert tiktok.feed_url() == "https://www.tiktok.com/foryou"
    assert tiktok.feed_url("@nasa") == "https://www.tiktok.com/@nasa"
    assert tiktok.is_on_feed("https://www.tiktok.com/foryou")
    assert not tiktok.is_on_feed("https://www.tiktok.com/login")


def test_junk_payloads():
    assert _clips(None) == []
    assert _clips({"itemList": [{"id": "x", "video": {}}]}) == []
