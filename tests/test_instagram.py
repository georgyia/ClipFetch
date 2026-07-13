from clipfetch.model import Clip, Quality
from clipfetch.platforms.instagram import Instagram

instagram = Instagram()

# Trimmed-down shape of Instagram's clips feed API responses.
FEED_PAYLOAD = {
    "items": [
        {
            "media": {
                "code": "ABC123",
                "caption": {"text": "space is cool #nasa"},
                "user": {"username": "nasa"},
                "like_count": 4321,
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
    clips = _clips(FEED_PAYLOAD)
    assert [(c.ident, c.video_url) for c in clips] == [
        ("ABC123", "https://cdn.test/abc_hi.mp4"),
        ("DEF456", "https://cdn.test/def.mp4"),
    ]


def test_find_clips_extracts_metadata_when_present():
    rich, bare = _clips(FEED_PAYLOAD)
    assert rich.url == "https://www.instagram.com/reel/ABC123/"
    assert rich.author == "nasa"
    assert rich.caption == "space is cool #nasa"
    assert rich.likes == 4321
    # DEF456 carries no caption/user/like_count — fields stay None, not junk.
    assert bare.url == "https://www.instagram.com/reel/DEF456/"
    assert bare.author is None and bare.caption is None and bare.likes is None


def test_metadata_ignores_malformed_fields():
    payload = {
        "media": {
            "code": "XYZ",
            "caption": "bare string, not the usual dict",
            "user": {"pk": 1},  # no username
            "like_count": "many",  # not an int
            "video_versions": [{"url": "https://cdn.test/x.mp4", "width": 720}],
        }
    }
    (clip,) = _clips(payload)
    assert clip.author is None and clip.caption is None and clip.likes is None


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


class _FakePermalinkPage:
    def __init__(self, context):
        self.context = context
        self.closed = False

    def goto(self, url, wait_until, timeout):
        assert wait_until == "commit"
        self.context.started.append(url.split("/reel/", 1)[1].split("/", 1)[0])

    def wait_for_timeout(self, _milliseconds):
        # Resolution only becomes possible after every navigation was started.
        self.context.wait_started_counts.append(len(self.context.started))
        for code in self.context.started:
            self.context.clips.setdefault(code, Clip("instagram", code, f"https://cdn/{code}"))

    def close(self):
        self.closed = True


class _FakePermalinkContext:
    def __init__(self, clips):
        self.clips = clips
        self.started = []
        self.wait_started_counts = []
        self.pages = []

    def new_page(self):
        page = _FakePermalinkPage(self)
        self.pages.append(page)
        return page


def test_permalink_batch_starts_all_tabs_before_waiting():
    clips = {}
    context = _FakePermalinkContext(clips)
    instagram._resolve_permalinks(context, ["AAA", "BBB", "CCC"], clips)

    assert context.started == ["AAA", "BBB", "CCC"]
    assert context.wait_started_counts == [3]
    assert list(clips) == ["AAA", "BBB", "CCC"]
    assert all(page.closed for page in context.pages)
