"""Regenerate the small project-owned OCR video corpus.

The committed MP4 files are the benchmark inputs. This script documents their
construction and is not run by normal tests.
"""

from __future__ import annotations

from pathlib import Path

import av
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1] / "tests/fixtures/visible_text"
WIDTH = 640
HEIGHT = 360
FPS = 2
FRAMES = 8
FONT_CANDIDATES = (
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
)


def _font(size: int):
    path = next((item for item in FONT_CANDIDATES if item.exists()), None)
    if path is None:
        raise RuntimeError("Arial Unicode or DejaVu Sans is required to regenerate fixtures")
    return ImageFont.truetype(str(path), size)


def _frame(
    text: str,
    *,
    foreground: str = "white",
    background: str = "#202030",
    size: int = 44,
    rotation: float = 0,
    x_offset: int = 0,
) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), background)
    if text:
        draw = ImageDraw.Draw(image)
        font = _font(size)
        box = draw.textbbox((0, 0), text, font=font)
        x = (WIDTH - (box[2] - box[0])) // 2 + x_offset
        y = (HEIGHT - (box[3] - box[1])) // 2
        draw.text((x, y), text, font=font, fill=foreground)
    if rotation:
        image = image.rotate(
            rotation,
            resample=Image.Resampling.BICUBIC,
            expand=False,
            fillcolor=background,
        )
    return image


def _write_video(name: str, images: list[Image.Image]) -> None:
    path = ROOT / name
    with av.open(str(path), "w") as container:
        stream = container.add_stream("mpeg4", rate=FPS)
        stream.width = WIDTH
        stream.height = HEIGHT
        stream.pix_fmt = "yuv420p"
        for image in images:
            for packet in stream.encode(av.VideoFrame.from_image(image)):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    _write_video("static_title.mp4", [_frame("BUILD YOUR STARTUP", size=54)] * FRAMES)
    _write_video(
        "moving_subtitles.mp4",
        [
            _frame("Learn from every failure", size=40, x_offset=index * 3 - 9)
            if index < FRAMES // 2
            else _frame("Ship the useful version", size=40, x_offset=index * 3 - 9)
            for index in range(FRAMES)
        ],
    )
    _write_video(
        "repeated_caption.mp4",
        [_frame("Validate with customers", size=40)] * FRAMES,
    )
    _write_video(
        "low_contrast.mp4",
        [
            _frame(
                "quiet product lesson",
                foreground="#888888",
                background="#777777",
                size=40,
            )
        ]
        * FRAMES,
    )
    _write_video("no_text.mp4", [_frame("", background="#225522")] * FRAMES)
    _write_video(
        "rotated_text.mp4",
        [_frame("ROTATED INSIGHT", rotation=25)] * FRAMES,
    )
    _write_video(
        "unicode.mp4",
        [_frame("Café • 東京 • مرحبا", background="#003355", size=42)] * FRAMES,
    )
    (ROOT / "corrupt.mp4").write_bytes(b"not a media container")


if __name__ == "__main__":
    main()
