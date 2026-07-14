from clipfetch.model import Quality
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
    assert [(c.ident, c.video_url, c.referer) for c in clips] == [
        ("7290000000000000001", "https://cdn.tt/hi.mp4", "https://www.tiktok.com/"),
        ("7290000000000000002", "https://cdn.tt/only.mp4", "https://www.tiktok.com/"),
    ]


def test_find_clips_extracts_metadata_when_present():
    payload = {
        "itemList": [
            {
                "id": "42",
                "desc": "check this out",
                "author": {"uniqueId": "cooluser", "nickname": "Cool User"},
                "stats": {"diggCount": 987, "playCount": 100000},
                "video": {"playAddr": "https://cdn.tt/42.mp4"},
            }
        ]
    }
    (clip,) = _clips(payload)
    assert clip.caption == "check this out"
    assert clip.author == "cooluser"
    assert clip.likes == 987
    assert clip.url == "https://www.tiktok.com/@cooluser/video/42"


def test_metadata_absent_stays_none():
    (first, second) = _clips(FEED_PAYLOAD)
    assert first.caption == "a clip"  # desc is present in the fixture
    assert first.author is None and first.likes is None and first.url is None
    assert second.caption is None and second.author is None


def test_extended_metadata_is_extracted_without_an_extra_request():
    payload = {
        "itemList": [
            {
                "id": "42",
                "desc": "Build it #Emprendimiento #STARTUP #startup",
                "createTime": "1767225600",
                "stats": {
                    "diggCount": 99,
                    "playCount": "1000",
                    "commentCount": 8,
                    "shareCount": 7,
                },
                "video": {"playAddr": "https://cdn.tt/42.mp4", "duration": 12},
            }
        ]
    }
    (clip,) = _clips(payload)
    assert clip.hashtags == ("emprendimiento", "startup")
    assert (clip.likes, clip.views, clip.comments_count, clip.shares) == (99, 1000, 8, 7)
    assert clip.duration_seconds == 12
    assert clip.published_at.isoformat() == "2026-01-01T00:00:00+00:00"


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
