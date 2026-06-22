"""Trace logo PNG color regions to SVG paths (PIL only, no deps)."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PNG = ROOT / "static" / "brand" / "logo-source.png"
OUT = ROOT / "static" / "brand" / "logo-traced-layers.json"


def mask_image(pred) -> Image.Image:
    im = Image.open(PNG).convert("RGBA")
    out = Image.new("L", im.size, 0)
    px = out.load()
    src = im.load()
    for y in range(im.height):
        for x in range(im.width):
            if pred(src[x, y]):
                px[x, y] = 255
    return out


def trace_contours(mask: Image.Image, min_points: int = 20) -> list[str]:
    """Moore-neighbor contour tracing on binary mask."""
    w, h = mask.size
    m = mask.load()
    visited: set[tuple[int, int]] = set()
    contours: list[list[tuple[int, int]]] = []

    def on(x: int, y: int) -> bool:
        return 0 <= x < w and 0 <= y < h and m[x, y] > 128

    for y in range(h):
        for x in range(w):
            if not on(x, y) or (x, y) in visited:
                continue
            stack = [(x, y)]
            comp: list[tuple[int, int]] = []
            while stack:
                cx, cy = stack.pop()
                if (cx, cy) in visited or not on(cx, cy):
                    continue
                visited.add((cx, cy))
                comp.append((cx, cy))
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if on(nx, ny) and (nx, ny) not in visited:
                        stack.append((nx, ny))
            if len(comp) >= min_points:
                comp.sort(key=lambda p: (p[1], p[0]))
                contours.append(comp)
    return contours


def contour_to_path(points: list[tuple[int, int]], simplify: int = 6) -> str:
    if not points:
        return ""
    step = max(1, len(points) // (len(points) // simplify + 1))
    sampled = points[::step]
    if sampled[0] != sampled[-1]:
        sampled.append(sampled[0])
    parts = [f"M {sampled[0][0]} {sampled[0][1]}"]
    for x, y in sampled[1:]:
        parts.append(f"L {x} {y}")
    parts.append("Z")
    return " ".join(parts)


def main() -> None:
    black = mask_image(lambda p: p[3] > 200 and p[0] < 90 and p[1] < 90 and p[2] < 90)
    green = mask_image(lambda p: p[3] > 200 and p[1] > 70 and p[1] > p[0] + 15 and p[1] > p[2])
    yellow = mask_image(
        lambda p: p[3] > 200 and p[0] > 170 and p[1] > 130 and p[2] < 130 and p[0] > p[2]
    )
    white = mask_image(
        lambda p: p[3] > 200 and p[0] > 215 and p[1] > 215 and p[2] > 210
        and not (p[1] > 70 and p[1] > p[0] + 15)
        and not (p[0] < 90 and p[1] < 90 and p[2] < 90)
    )

    layers = {}
    for name, mask in (("black", black), ("green", green), ("yellow", yellow), ("white", white)):
        comps = trace_contours(mask, min_points=30)
        comps.sort(key=len, reverse=True)
        layers[name] = [
            {"points": len(c), "path": contour_to_path(c, simplify=8)}
            for c in comps[:12]
        ]
        print(name, "components", len(comps), "largest", comps[0] if comps else 0)

    OUT.write_text(json.dumps(layers, indent=2), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
