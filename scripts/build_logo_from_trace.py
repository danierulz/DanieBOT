"""Build brand_logo SVG paths from traced PNG layers."""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "static" / "brand" / "logo-traced-layers.json"
OUT_PATH = ROOT / "static" / "brand" / "logo-generated-fragment.html"


def centroid_from_path(path: str) -> tuple[float, float]:
    nums = [float(x) for x in path.replace("M", " ").replace("L", " ").replace("Z", " ").split() if x]
    xs = nums[0::2]
    ys = nums[1::2]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def main() -> None:
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    black = data["black"]
    green = sorted(data["green"], key=lambda x: x["points"], reverse=True)
    yellow = data["yellow"][0]["path"] if data["yellow"] else ""
    yc = centroid_from_path(yellow) if yellow else (170, 367)

    white_near = []
    for item in data["white"]:
        if item["points"] > 5000:
            continue
        c = centroid_from_path(item["path"])
        if dist(c, yc) < 120:
            white_near.append(item)
    white_near.sort(key=lambda x: x["points"], reverse=True)

    letter_o = black[0]["path"]
    letter_j = black[1]["path"] if len(black) > 1 else ""

    # green: largest blob often stem+leaves merged; use top 5 by points
    green_paths = [g["path"] for g in green[:6]]

    lines = [
        '<svg viewBox="0 0 666 714" xmlns="http://www.w3.org/2000/svg">',
        f'  <path class="brand-logo__letter-o" d="{letter_o}" fill-rule="evenodd"/>',
    ]
    if letter_j:
        lines.append(f'  <path class="brand-logo__letter-j" d="{letter_j}"/>')
    if green_paths:
        lines.append(f'  <path class="brand-logo__stem" d="{green_paths[0]}" fill="none"/>')
    for i, gp in enumerate(green_paths[1:5], start=1):
        lines.append(f'  <path class="brand-logo__leaf brand-logo__leaf--{i}" d="{gp}"/>')
    for i, wp in enumerate(white_near[:5], start=1):
        lines.append(f'  <path class="brand-logo__petal brand-logo__petal--{i}" d="{wp}"/>')
    if yellow:
        lines.append(f'  <path class="brand-logo__flower-center" d="{yellow}"/>')
    lines.append("</svg>")
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print("letter_o points", black[0]["points"])
    print("letter_j points", black[1]["points"] if len(black) > 1 else 0)
    print("green parts", len(green_paths))
    print("white petals", len(white_near))
    print("wrote", OUT_PATH)


if __name__ == "__main__":
    main()
