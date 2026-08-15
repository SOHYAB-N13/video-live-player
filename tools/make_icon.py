"""Generate app.ico for the live video player branding.

Requires Pillow::

    pip install pillow
    python tools/make_icon.py

Produces ``app.ico`` in the repository root with sizes
16, 24, 32, 48, 64, 128 and 256 px.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "app.ico"
RED = (220, 38, 38, 255)
WHITE = (255, 255, 255, 255)
SIZES = [16, 24, 32, 48, 64, 128, 256]
CORNER_RATIO = 0.25


def draw(size: int) -> Image.Image:
    """Draw a red rounded square with a white play triangle."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = max(1, int(size * CORNER_RATIO))
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=RED)
    tri_w = int(size * 0.42)
    tri_h = int(size * 0.5)
    top = (size - tri_h) // 2
    left = int(size * 0.31)
    right = left + tri_w
    draw.polygon([(left, top), (left, top + tri_h), (right, size // 2)], fill=WHITE)
    return img


def main() -> None:
    images = [draw(s) for s in SIZES]
    images[-1].save(OUT, format="ICO", sizes=[(s, s) for s in SIZES], append_images=images[:-1])
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
