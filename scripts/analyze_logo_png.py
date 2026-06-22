"""Analyze logo-source.png bounds by color (PIL only)."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PNG = ROOT / "static" / "brand" / "logo-source.png"


def bounds_for(pred) -> tuple[int, int, int, int] | None:
    im = Image.open(PNG).convert("RGBA")
    xs: list[int] = []
    ys: list[int] = []
    for y in range(im.height):
        for x in range(im.width):
            if pred(im.getpixel((x, y))):
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def main() -> None:
    im = Image.open(PNG)
    print("size", im.size)

    def is_black(px):
        r, g, b, a = px
        return a > 200 and r < 90 and g < 90 and b < 90

    def is_green(px):
        r, g, b, a = px
        return a > 200 and g > 70 and g > r + 15 and g > b

    def is_white_petal(px):
        r, g, b, a = px
        return a > 200 and r > 210 and g > 210 and b > 200 and not is_green(px) and not is_black(px)

    def is_yellow(px):
        r, g, b, a = px
        return a > 200 and r > 180 and g > 150 and b < 120

    for name, fn in (
        ("black", is_black),
        ("green", is_green),
        ("white", is_white_petal),
        ("yellow", is_yellow),
    ):
        b = bounds_for(fn)
        print(name, b)


if __name__ == "__main__":
    main()
