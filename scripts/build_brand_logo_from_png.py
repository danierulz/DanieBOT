"""Extrae geometría de logo-source.png y genera brand_logo.html."""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from skimage import morphology
from skimage.measure import approximate_polygon, find_contours, grid_points_in_poly, label, regionprops

ROOT = Path(__file__).resolve().parents[1]
PNG = ROOT / "static" / "brand" / "logo-source.png"
JSON_OUT = ROOT / "static" / "brand" / "logo-extracted.json"
CALIBRATION = ROOT / "static" / "brand" / "logo-calibration.json"
HTML_OUT = ROOT / "templates" / "partials" / "brand_logo.html"
META_OUT = ROOT / "static" / "brand" / "logo-meta.json"

VIEW_W, VIEW_H = 666, 714
PETAL_SECTORS = 5
MAX_LEAVES = 6
LETTER_ZONE_X = 280


@dataclass
class LayerPath:
    cls: str
    d: str
    kind: str = "path"
    cx: float | None = None
    cy: float | None = None
    r: float | None = None
    path_length: float | None = None
    transform: str | None = None
    style: str | None = None


@dataclass
class ExtractedLogo:
    view_box: str = f"0 0 {VIEW_W} {VIEW_H}"
    stem_length: float = 520.0
    leaf_count: int = 0
    bud_count: int = 0
    petal_count: int = 0
    letters: list[LayerPath] = field(default_factory=list)
    jasmine: list[LayerPath] = field(default_factory=list)


def _load_rgba() -> np.ndarray:
    return np.array(Image.open(PNG).convert("RGBA"))


def _black_mask(rgba: np.ndarray) -> np.ndarray:
    r, g, b, a = rgba[..., 0], rgba[..., 1], rgba[..., 2], rgba[..., 3]
    return (a > 200) & (r < 90) & (g < 90) & (b < 90)


def _green_mask(rgba: np.ndarray) -> np.ndarray:
    r, g, b, a = rgba[..., 0], rgba[..., 1], rgba[..., 2], rgba[..., 3]
    return (a > 200) & (g > 70) & (g > (r + 15)) & (g > b)


def _yellow_mask(rgba: np.ndarray) -> np.ndarray:
    r, g, b, a = rgba[..., 0], rgba[..., 1], rgba[..., 2], rgba[..., 3]
    return (a > 200) & (r > 170) & (g > 130) & (b < 130) & (r > b)


def _near_white_mask(rgba: np.ndarray) -> np.ndarray:
    r, g, b, a = rgba[..., 0], rgba[..., 1], rgba[..., 2], rgba[..., 3]
    return (a > 200) & (r > 200) & (g > 200) & (b > 195)


def _simplify_contour(contour: np.ndarray, tolerance: float = 2.5) -> np.ndarray:
    if len(contour) < 4:
        return contour
    simplified = approximate_polygon(contour, tolerance=tolerance)
    if len(simplified) < 3:
        return contour
    return simplified


def _clean_contour(contour: np.ndarray, min_step: float = 2.0) -> np.ndarray:
    """Drop duplicate and nearly-collinear points."""
    if len(contour) < 3:
        return contour
    pts = [(float(y), float(x)) for y, x in contour]
    cleaned = [pts[0]]
    for pt in pts[1:]:
        if math.hypot(pt[0] - cleaned[-1][0], pt[1] - cleaned[-1][1]) >= min_step:
            cleaned.append(pt)
    if len(cleaned) < 3:
        return contour
    return np.array([[y, x] for y, x in cleaned])


def _contour_to_path_d(contour: np.ndarray) -> str:
    contour = _clean_contour(_simplify_contour(contour))
    pts = [(float(x), float(y)) for y, x in contour]
    if not pts:
        return ""
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    parts = [f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"]
    for x, y in pts[1:]:
        parts.append(f"L {x:.1f} {y:.1f}")
    parts.append("Z")
    return " ".join(parts)


def _polyline_length(points: np.ndarray) -> float:
    if len(points) < 2:
        return 0.0
    return float(
        sum(
            math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1])
            for i in range(1, len(points))
        )
    )


def _stem_polyline_d(points: np.ndarray) -> str:
    parts = [f"M {points[0][0]:.1f} {points[0][1]:.1f}"]
    for x, y in points[1:]:
        parts.append(f"L {x:.1f} {y:.1f}")
    return " ".join(parts)


def _largest_black_component(black: np.ndarray) -> np.ndarray:
    labeled = label(black)
    props = sorted(regionprops(labeled), key=lambda p: p.area, reverse=True)
    if not props:
        return black
    return labeled == props[0].label


def _split_o_and_j(black: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    eroded = morphology.erosion(black, morphology.disk(3))
    labeled = label(eroded)
    props = sorted(regionprops(labeled), key=lambda p: p.area, reverse=True)
    if not props:
        return black, np.zeros_like(black, dtype=bool)
    o_eroded = labeled == props[0].label
    o_mask = morphology.dilation(o_eroded, morphology.disk(3)) & black
    j_labeled = label(black & ~o_mask)
    j_props = sorted(regionprops(j_labeled), key=lambda p: p.area, reverse=True)
    j_mask = np.zeros_like(black, dtype=bool)
    if j_props:
        main_j = max(
            (p for p in j_props if p.area >= 400 and p.centroid[1] < VIEW_W * 0.65),
            key=lambda p: p.area,
            default=None,
        )
        if main_j is not None:
            j_mask = j_labeled == main_j.label
    return o_mask, j_mask


def _closed_o_ring(main: np.ndarray, j_mask: np.ndarray) -> np.ndarray:
    o_ring = main & ~j_mask
    closed = morphology.closing(o_ring, morphology.disk(6))
    labeled = label(closed)
    props = sorted(regionprops(labeled), key=lambda p: p.area, reverse=True)
    if not props:
        return o_ring
    ring = labeled == props[0].label
    return ring & morphology.dilation(main, morphology.disk(1))


def _inner_o_hole_mask(main: np.ndarray, o_ring: np.ndarray, rgba: np.ndarray) -> np.ndarray:
    outer_cs = find_contours(main.astype(float), 0.5)
    if not outer_cs:
        return np.zeros_like(main, dtype=bool)
    outer = max(outer_cs, key=len)
    inside = grid_points_in_poly((VIEW_H, VIEW_W), outer).reshape(VIEW_H, VIEW_W)
    near_white = _near_white_mask(rgba)
    black = _black_mask(rgba)
    green = _green_mask(rgba)
    cavity = inside & near_white & ~black & ~green
    labeled = label(cavity)
    props = sorted(regionprops(labeled), key=lambda p: p.area, reverse=True)
    if not props:
        return cavity
    bbox = regionprops(label(main))[0].bbox
    cy = (bbox[0] + bbox[2]) / 2
    cx = (bbox[1] + bbox[3]) / 2
    best = None
    best_score = -1.0
    for prop in props[:6]:
        if prop.area < 800:
            continue
        dist = math.hypot(prop.centroid[1] - cx, prop.centroid[0] - cy)
        if dist > 120:
            continue
        score = prop.area - dist * 2
        if score > best_score:
            best_score = score
            best = prop
    if best is None:
        return cavity
    hole = labeled == best.label
    return hole & morphology.dilation(o_ring, morphology.disk(2))


def _letter_o_path(main: np.ndarray, o_ring: np.ndarray, rgba: np.ndarray) -> str | None:
    outer_cs = find_contours(o_ring.astype(float), 0.5)
    if not outer_cs:
        return None
    outer = _simplify_contour(max(outer_cs, key=len), tolerance=5.0)
    parts = [_contour_to_path_d(outer)]

    filled = ndimage.binary_fill_holes(o_ring)
    ring_hole = filled & ~o_ring
    if ring_hole.any():
        inner_cs = find_contours(ring_hole.astype(float), 0.5)
        if inner_cs:
            inner = _simplify_contour(max(inner_cs, key=len), tolerance=4.0)
            parts.append(_contour_to_path_d(inner))
    else:
        hole = _inner_o_hole_mask(main, o_ring, rgba)
        if hole.any():
            inner_cs = find_contours(hole.astype(float), 0.5)
            if inner_cs:
                inner = _simplify_contour(max(inner_cs, key=len), tolerance=4.0)
                parts.append(_contour_to_path_d(inner))
    return " ".join(parts)


def _extract_letters(black: np.ndarray, rgba: np.ndarray) -> tuple[list[LayerPath], np.ndarray, np.ndarray]:
    layers: list[LayerPath] = []
    main = _largest_black_component(black)
    o_mask, j_mask = _split_o_and_j(black)
    o_ring = _closed_o_ring(main, j_mask)

    o_path = _letter_o_path(main, o_ring, rgba)
    if o_path:
        layers.append(LayerPath(cls="brand-logo__letter-o", d=o_path, kind="evenodd"))

    if j_mask.any():
        jc = find_contours(j_mask.astype(float), 0.5)
        if jc:
            c = _simplify_contour(max(jc, key=len), tolerance=4.0)
            layers.append(LayerPath(cls="brand-logo__letter-j", d=_contour_to_path_d(c)))

    return layers, o_ring | j_mask, j_mask


def _skeleton_path(mask: np.ndarray) -> tuple[str, float] | None:
    if mask.sum() < 30:
        return None
    skel = morphology.skeletonize(mask)
    ys, xs = np.where(skel)
    if len(xs) < 2:
        return None

    y_min, y_max = int(ys.min()), int(ys.max())
    edges = np.linspace(y_min, y_max, 36)
    prev_x = float(np.median(xs))
    pts: list[tuple[float, float]] = []
    for i in range(len(edges) - 1):
        sel = (ys >= edges[i]) & (ys < edges[i + 1])
        if not np.any(sel):
            continue
        band_xs = xs[sel]
        idx = int(np.argmin(np.abs(band_xs.astype(float) - prev_x)))
        px = float(band_xs[idx])
        py = float((edges[i] + edges[i + 1]) / 2)
        pts.append((px, py))
        prev_x = px

    if len(pts) < 2:
        return None
    pts.sort(key=lambda p: -p[1])
    arr = approximate_polygon(np.array(pts, dtype=float), tolerance=4.0)
    if len(arr) < 2:
        arr = np.array(pts, dtype=float)
    return _stem_polyline_d(arr), _polyline_length(arr)


def _stem_skeleton_points(mask: np.ndarray) -> np.ndarray | None:
    skel = morphology.skeletonize(mask)
    ys, xs = np.where(skel)
    if len(xs) == 0:
        return None
    return np.column_stack([xs.astype(float), ys.astype(float)])


def _min_dist_to_stem(prop, stem_pts: np.ndarray) -> float:
    cy, cx = prop.centroid
    return float(np.min(np.hypot(stem_pts[:, 0] - cx, stem_pts[:, 1] - cy)))


def _white_in_rect(
    rgba: np.ndarray, x0: int, y0: int, x1: int, y1: int, flower_center: tuple[float, float]
) -> tuple[np.ndarray, float] | None:
    near_white = _near_white_mask(rgba)
    black = _black_mask(rgba)
    green = _green_mask(rgba)
    sub = near_white[y0:y1, x0:x1] & ~black[y0:y1, x0:x1] & ~green[y0:y1, x0:x1]
    labeled = label(sub)
    props = sorted(regionprops(labeled), key=lambda p: p.area, reverse=True)
    for prop in props:
        if prop.area < 40:
            continue
        bbox = prop.bbox
        h = bbox[2] - bbox[0]
        w = bbox[3] - bbox[1]
        if h / max(w, 1) < 1.0:
            continue
        mask = np.zeros(rgba.shape[:2], dtype=bool)
        mask[y0:y1, x0:x1] = labeled == prop.label
        wc = find_contours(mask.astype(float), 0.5)
        if not wc:
            continue
        c = _simplify_contour(max(wc, key=len), tolerance=2.0)
        cy, cx = prop.centroid
        return c, float(cy + y0), float(cx + x0)
    return None


def _radial_petal_contours(
    rgba: np.ndarray, flower_center: tuple[float, float], sectors: int = PETAL_SECTORS
) -> list[tuple[np.ndarray, float, float]]:
    cx, cy = flower_center
    yy, xx = np.mgrid[0 : rgba.shape[0], 0 : rgba.shape[1]]
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    angles = np.arctan2(yy - cy, xx - cx)
    near_white = _near_white_mask(rgba)
    black = _black_mask(rgba)
    green = _green_mask(rgba)
    base = (dist >= 18) & (dist <= 68) & near_white & ~black & ~green

    petals: list[tuple[np.ndarray, float, float]] = []
    slice_rad = 2 * math.pi / sectors
    offset = -math.pi / 2
    for i in range(sectors):
        a0 = offset + i * slice_rad
        a1 = offset + (i + 1) * slice_rad
        sector = base.copy()
        if a0 <= a1:
            sector &= (angles >= a0) & (angles < a1)
        else:
            sector &= (angles >= a0) | (angles < a1)
        if sector.sum() < 40:
            continue
        labeled = label(sector)
        props = sorted(regionprops(labeled), key=lambda p: p.area, reverse=True)
        if not props or props[0].area < 40:
            continue
        pmask = labeled == props[0].label
        pc = find_contours(pmask.astype(float), 0.5)
        if not pc:
            continue
        c = _simplify_contour(max(pc, key=len), tolerance=2.0)
        pcy, pcx = props[0].centroid
        petals.append((c, float(pcy), float(pcx)))
    return petals


def _extract_jasmine(
    rgba: np.ndarray,
    green: np.ndarray,
    yellow: np.ndarray,
    letter_mask: np.ndarray,
) -> tuple[list[LayerPath], float]:
    layers: list[LayerPath] = []
    green = green & ~letter_mask
    labeled = label(green)
    props = sorted(regionprops(labeled), key=lambda p: p.area, reverse=True)
    if not props:
        return layers, 520.0

    stem_prop = max(
        props,
        key=lambda p: (p.bbox[2] - p.bbox[0]) + (p.bbox[3] - p.bbox[1]) + p.area * 0.01,
    )
    stem_mask = labeled == stem_prop.label
    stem_pts = _stem_skeleton_points(stem_mask)
    stem_result = _skeleton_path(stem_mask)
    stem_len = 420.0
    if stem_result:
        d, stem_len = stem_result
        layers.append(LayerPath(cls="brand-logo__stem", d=d, path_length=round(stem_len, 1)))

    leaf_idx = 0
    leaf_props = []
    for prop in props:
        if prop.label == stem_prop.label or prop.area < 120:
            continue
        if prop.centroid[1] > LETTER_ZONE_X:
            continue
        if stem_pts is not None and _min_dist_to_stem(prop, stem_pts) > 55:
            continue
        leaf_props.append(prop)
    leaf_props.sort(key=lambda p: p.centroid[0])

    for prop in leaf_props:
        leaf_idx += 1
        if leaf_idx > MAX_LEAVES:
            break
        lmask = labeled == prop.label
        lc = find_contours(lmask.astype(float), 0.5)
        if not lc:
            continue
        c = _simplify_contour(max(lc, key=len), tolerance=2.0)
        delay = 0.5 + (leaf_idx - 1) * 0.12
        layers.append(
            LayerPath(
                cls=f"brand-logo__leaf brand-logo__leaf--{leaf_idx}",
                d=_contour_to_path_d(c),
                style=f"--leaf-delay: {delay:.2f}s",
            )
        )

    yellow_props = regionprops(label(yellow))
    flower_center = (179.0, 346.0)
    if yellow_props:
        yp = max(yellow_props, key=lambda p: p.area)
        flower_center = (float(yp.centroid[1]), float(yp.centroid[0]))
        center_delay = 0.5 + leaf_idx * 0.12 + 0.55
        layers.append(
            LayerPath(
                cls="brand-logo__flower-center",
                d="",
                kind="circle",
                cx=flower_center[0],
                cy=flower_center[1],
                r=max(4.0, math.sqrt(yp.area / math.pi) * 0.85),
                style=f"--center-delay: {center_delay:.2f}s",
            )
        )

    fcx, fcy = flower_center
    bud_specs = [
        ("brand-logo__bud brand-logo__bud--top", int(fcx - 35), int(fcy - 95), int(fcx + 35), int(fcy - 45)),
        ("brand-logo__bud brand-logo__bud--mid", int(fcx - 30), int(fcy + 35), int(fcx + 30), int(fcy + 85)),
    ]
    bud_delay_base = 0.5 + leaf_idx * 0.12 + 0.08
    bud_count = 0
    for cls, x0, y0, x1, y1 in bud_specs:
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(VIEW_W, x1), min(VIEW_H, y1)
        found = _white_in_rect(rgba, x0, y0, x1, y1, flower_center)
        if not found:
            continue
        c, _cy, _cx = found
        delay = bud_delay_base + bud_count * 0.1
        layers.append(LayerPath(cls=cls, d=_contour_to_path_d(c), style=f"--bud-delay: {delay:.2f}s"))
        bud_count += 1

    petal_delay_base = bud_delay_base + bud_count * 0.1 + 0.1
    radial_petals = _radial_petal_contours(rgba, flower_center)
    for petals, (c, pcy, pcx) in enumerate(radial_petals[:PETAL_SECTORS]):
        angle = math.degrees(math.atan2(pcy - fcy, pcx - fcx))
        layers.append(
            LayerPath(
                cls=f"brand-logo__petal brand-logo__petal--{petals + 1}",
                d=_contour_to_path_d(c),
                transform=f"rotate({angle:.1f} {pcx:.1f} {pcy:.1f})",
                style=f"--petal-delay: {petal_delay_base:.2f}s",
            )
        )

    return layers, stem_len


def extract_logo() -> ExtractedLogo:
    rgba = _load_rgba()
    black = _black_mask(rgba)
    green = _green_mask(rgba)
    yellow = _yellow_mask(rgba)

    letters, letter_mask, _j_mask = _extract_letters(black, rgba)
    jasmine, stem_len = _extract_jasmine(rgba, green, yellow, letter_mask)

    leaf_count = sum(1 for layer in jasmine if "brand-logo__leaf--" in layer.cls)
    bud_count = sum(1 for layer in jasmine if "brand-logo__bud" in layer.cls)
    petal_count = sum(1 for layer in jasmine if "brand-logo__petal--" in layer.cls)
    letter_o_delay = 0.5 + leaf_count * 0.12 + 0.5 + min(bud_count, 2) * 0.1 + 0.65
    letter_j_delay = letter_o_delay + 0.15
    for layer in letters:
        if layer.cls == "brand-logo__letter-o":
            layer.style = f"--letter-delay: {letter_o_delay:.2f}s"
        elif layer.cls == "brand-logo__letter-j":
            layer.style = f"--letter-delay: {letter_j_delay:.2f}s"

    return ExtractedLogo(
        stem_length=stem_len,
        leaf_count=leaf_count,
        bud_count=bud_count,
        petal_count=petal_count,
        letters=letters,
        jasmine=jasmine,
    )


def _load_calibration() -> dict:
    if not CALIBRATION.exists():
        return {
            "letters": {"tx": 0, "ty": 0, "scale": 1},
            "jasmine": {"tx": 0, "ty": 0, "scale": 1},
        }
    return json.loads(CALIBRATION.read_text(encoding="utf-8"))


def _transform_attr(group: dict) -> str:
    tx = group.get("tx", 0)
    ty = group.get("ty", 0)
    scale = group.get("scale", 1)
    parts = []
    if tx or ty:
        parts.append(f"translate({tx} {ty})")
    if scale != 1:
        parts.append(f"scale({scale})")
    return f' transform="{" ".join(parts)}"' if parts else ""


def _render_path(layer: LayerPath) -> str:
    style_attr = f' style="{layer.style}"' if layer.style else ""
    if layer.kind == "circle":
        return (
            f'    <circle class="{layer.cls}" cx="{layer.cx:.1f}" cy="{layer.cy:.1f}"'
            f' r="{layer.r:.1f}"{style_attr} />'
        )
    extra = ""
    if layer.path_length is not None:
        extra += f' pathLength="{layer.path_length:.1f}"'
    if layer.transform:
        extra += f' transform="{layer.transform}"'
    fill_rule = ' fill-rule="evenodd"' if layer.kind == "evenodd" else ""
    return f'    <path class="{layer.cls}" d="{layer.d}"{fill_rule}{extra}{style_attr} />'


def render_html(data: ExtractedLogo) -> str:
    cal = _load_calibration()
    lines = [
        "<svg",
        '  class="brand-logo{% if not brand_logo_animated %} brand-logo--instant{% endif %}"',
        '  xmlns="http://www.w3.org/2000/svg"',
        f'  viewBox="{data.view_box}"',
        '  role="img"',
        '  aria-hidden="true"',
        '  style="--logo-letter: {{ brand_logo_colors.letter }}; --logo-stem: {{ brand_logo_colors.stem }}; --logo-leaf: {{ brand_logo_colors.leaf }}; --logo-petal: {{ brand_logo_colors.petal }}; --logo-petal-center: {{ brand_logo_colors.petal_center }}; --logo-bud: {{ brand_logo_colors.bud }}; --logo-stem-length: '
        + f"{data.stem_length:.1f};\"",
        ">",
        f'  <g class="brand-logo__letters"{_transform_attr(cal.get("letters", {}))}>',
    ]
    for layer in data.letters:
        lines.append(_render_path(layer))
    lines.append("  </g>")
    lines.append(f'  <g class="brand-logo__jasmine"{_transform_attr(cal.get("jasmine", {}))}>')
    for layer in data.jasmine:
        lines.append(_render_path(layer))
    lines.append("  </g>")
    lines.append("</svg>")
    lines.append("")
    return "\n".join(lines)


def to_json(data: ExtractedLogo) -> dict:
    def layer_dict(layer: LayerPath) -> dict:
        d = {"cls": layer.cls, "d": layer.d, "kind": layer.kind}
        if layer.cx is not None:
            d["cx"] = layer.cx
            d["cy"] = layer.cy
            d["r"] = layer.r
        if layer.path_length is not None:
            d["path_length"] = layer.path_length
        if layer.transform:
            d["transform"] = layer.transform
        if layer.style:
            d["style"] = layer.style
        return d

    return {
        "view_box": data.view_box,
        "stem_length": data.stem_length,
        "leaf_count": data.leaf_count,
        "bud_count": data.bud_count,
        "petal_count": data.petal_count,
        "letters": [layer_dict(x) for x in data.letters],
        "jasmine": [layer_dict(x) for x in data.jasmine],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build brand logo SVG from PNG")
    parser.add_argument("--write-html", action="store_true", help="Write templates/partials/brand_logo.html")
    parser.add_argument("--json-only", action="store_true", help="Only write logo-extracted.json")
    args = parser.parse_args()

    data = extract_logo()
    JSON_OUT.write_text(json.dumps(to_json(data), indent=2), encoding="utf-8")
    META_OUT.write_text(
        json.dumps(
            {
                "stem_length": data.stem_length,
                "leaf_count": data.leaf_count,
                "bud_count": data.bud_count,
                "petal_count": data.petal_count,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {JSON_OUT}")
    print(
        f"stem={data.stem_length:.1f} leaves={data.leaf_count} buds={data.bud_count} petals={data.petal_count}"
    )

    if args.write_html or not args.json_only:
        HTML_OUT.write_text(render_html(data), encoding="utf-8")
        print(f"Wrote {HTML_OUT}")


if __name__ == "__main__":
    main()
