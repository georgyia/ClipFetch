from clipfetch.model import Clip, Quality
from clipfetch.platforms.instagram import Instagram

instagram = Instagram()

# Trimmed-down shape of Instagram's clips feed API responses.
FEED_PAYLOAD = {
    "items": [
        {
            "media": {
                "code": "ABC123",
                "video_versions": [
                    {"url": "https://cdn.test/abc_low.mp4", "width": 480},
                    {"url": "https://cdn.test/abc_mid.mp4", "width": 720},
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
}


def _clips(payload, quality=Quality.HIGH):
    return list(instagram.find_clips(payload, quality))


def test_find_clips_picks_best_quality_and_skips_photos():
    assert _clips(FEED_PAYLOAD) == [
        Clip("instagram", "ABC123", "https://cdn.test/abc_hi.mp4"),
        Clip("instagram", "DEF456", "https://cdn.test/def.mp4"),
    ]


def test_quality_selection():
    assert _clips(FEED_PAYLOAD, Quality.LOW)[0].video_url == "https://cdn.test/abc_low.mp4"
    assert _clips(FEED_PAYLOAD, Quality.MEDIUM)[0].video_url == "https://cdn.test/abc_mid.mp4"
    assert _clips(FEED_PAYLOAD, Quality.HIGH)[0].video_url == "https://cdn.test/abc_hi.mp4"


def test_find_clips_handles_junk_payloads():
    assert _clips(None) == []
    assert _clips({"status": "ok"}) == []
    assert _clips([1, "x", {"code": "NOVIDEO"}]) == []
    assert _clips({"media": {"code": "X", "video_versions": []}}) == []


def test_feed_url_and_target_routing():
    assert instagram.feed_url() == "https://www.instagram.com/reels/"
    assert instagram.feed_url("@nasa") == "https://www.instagram.com/nasa/reels/"
    assert instagram.is_on_feed("https://www.instagram.com/reels/?x=1")
    assert not instagram.is_on_feed("https://www.instagram.com/")


class _FakeGridPage:
    """Minimal page double: serves reel hrefs and ignores scroll calls."""

    def __init__(self, hrefs):
        self._hrefs = hrefs

    def eval_on_selector_all(self, selector, script):
        return self._hrefs

    def mouse(self):  # pragma: no cover - attribute placeholder
        ...

    wheel = staticmethod(lambda *a, **k: None)
    evaluate = staticmethod(lambda *a, **k: None)
    wait_for_timeout = staticmethod(lambda *a, **k: None)


def test_harvest_shortcodes_dedupes_and_skips_known():
    page = _FakeGridPage(
        ["/reel/AAA/", "/reel/BBB/?x=1", "/reel/AAA/", "/p/PHOTO/", "/reel/CCC/"]
    )
    page.mouse = type("M", (), {"wheel": staticmethod(lambda *a, **k: None)})()
    codes = instagram._harvest_shortcodes(page, count=10, already_have={"BBB"})
    assert codes == ["AAA", "CCC"]  # BBB already have; photo link ignored
