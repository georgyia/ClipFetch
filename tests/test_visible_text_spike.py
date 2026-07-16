from scripts.visible_text_spike import (
    MAX_DECODED_FRAMES_PER_SAMPLE,
    MAX_RETAINED_CHARACTERS,
    MAX_SAMPLED_FRAMES,
    RapidOCRSpike,
    Segment,
    UnsupportedMedia,
    retain_lines,
    sample_timestamps,
)


def test_spike_sampling_is_strictly_bounded():
    assert sample_timestamps(5.0) == (0.0, 2.0, 4.0)
    assert len(sample_timestamps(10_000)) == MAX_SAMPLED_FRAMES
    try:
        sample_timestamps(float("inf"))
    except UnsupportedMedia:
        pass
    else:
        raise AssertionError("non-finite duration must be rejected")


def test_spike_seek_decode_has_a_hard_cap():
    class Frame:
        pts = 0

        def to_ndarray(self, format):
            return format

    class Stream:
        time_base = 1

    class Container:
        decoded = 0

        def seek(self, *args, **kwargs):
            pass

        def decode(self, stream):
            for _ in range(1000):
                self.decoded += 1
                yield Frame()

    container = Container()
    spike = object.__new__(RapidOCRSpike)
    sampled = spike._sample_frame(container, Stream(), 500.0)
    assert sampled.image == "bgr24"
    assert container.decoded == MAX_DECODED_FRAMES_PER_SAMPLE


def test_spike_threshold_deduplication_and_retained_text_cap():
    result = retain_lines(
        [
            Segment(0.0, "Build  your startup", 0.91),
            Segment(2.0, "Build your startup!", 0.99),
            Segment(4.0, "incomplete mixed script", 0.81),
            Segment(6.0, "Ａ" * (MAX_RETAINED_CHARACTERS + 50), 0.95),
        ]
    )
    assert result.segments[0].timestamp_seconds == 2.0
    assert "incomplete" not in result.text
    assert len(result.text) == MAX_RETAINED_CHARACTERS
