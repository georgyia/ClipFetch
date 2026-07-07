from clipfetch.model import Clip, Quality
from clipfetch.platforms.youtube import YouTubeShorts

yt = YouTubeShorts()

PLAYER_RESPONSE = {
    "videoDetails": {"videoId": "abc123", "title": "a short"},
    "streamingData": {
        "formats": [
            {"itag": 18, "mimeType": "video/mp4; codecs=\"avc1\"", "height": 360,
             "url": "https://rr.googlevideo.com/360.mp4"},
            {"itag": 22, "mimeType": "video/mp4; codecs=\"avc1\"", "height": 720,
             "url": "https://rr.googlevideo.com/720.mp4"},
            {"itag": 999, "mimeType": "video/mp4", "height": 1080,
             "signatureCipher": "s=xxx&url=cipher"},  # ciphered: no direct url
        ],
        "adaptiveFormats": [
            {"mimeType": "video/webm", "url": "https://rr.googlevideo.com/dash-only.webm"},
        ],
    },
}


def _clips(payload, quality=Quality.HIGH):
    return list(yt.find_clips(payload, quality))


def test_extracts_progressive_url_and_skips_ciphered():
    clips = _clips(PLAYER_RESPONSE)
    assert clips == [
        Clip("youtube", "abc123", "https://rr.googlevideo.com/720.mp4", referer="https://www.youtube.com/"),
    ]


def test_quality_selection():
    assert _clips(PLAYER_RESPONSE, Quality.LOW)[0].video_url == "https://rr.googlevideo.com/360.mp4"


def test_no_progressive_url_yields_nothing():
    ciphered_only = {
        "videoDetails": {"videoId": "x"},
        "streamingData": {"formats": [{"mimeType": "video/mp4", "signatureCipher": "s=1"}]},
    }
    assert _clips(ciphered_only) == []


def test_feed_and_target_urls():
    assert yt.feed_url() == "https://www.youtube.com/shorts"
    assert yt.feed_url("@mrbeast") == "https://www.youtube.com/@mrbeast/shorts"
    assert yt.is_on_feed("https://www.youtube.com/shorts/abc123")
