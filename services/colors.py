import json
import re
import unicodedata
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from database.models.Color import Color
from database.models.ProductColor import ProductColor


def normalize_color_code(label: str) -> str:
    raw = (label or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="El nombre del color no puede estar vacío.")
    normalized = unicodedata.normalize("NFKD", raw)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    code = re.sub(r"[^A-Za-z0-9]+", "_", ascii_only).strip("_").upper()
    if not code:
        code = re.sub(r"[^A-Z0-9]+", "_", raw.upper()).strip("_")
    if not code:
        raise HTTPException(status_code=400, detail="No se pudo generar un código para el color.")
    return code[:32]


def parse_colors_json(raw: Optional[str]) -> List[int]:
    if not raw or not str(raw).strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    ids: List[int] = []
    for x in data:
        if isinstance(x, int):
            ids.append(x)
        elif isinstance(x, str) and x.isdigit():
            ids.append(int(x))
        elif isinstance(x, dict) and x.get("color_id") is not None:
            ids.append(int(x["color_id"]))
    return list(dict.fromkeys(ids))


def color_to_public(c: Color) -> dict:
    return {
        "color_id": c.color_id,
        "code": c.code,
        "label": c.label,
        "hex": c.hex,
    }


def list_colors_public(db: Session) -> List[dict]:
    rows = db.query(Color).order_by(Color.sort_order.asc(), Color.label.asc()).all()
    return [color_to_public(c) for c in rows]


def colors_for_product(db: Session, product_id: int, *, active_only: bool = True) -> List[Color]:
    q = (
        db.query(Color)
        .join(ProductColor, ProductColor.color_id == Color.color_id)
        .filter(ProductColor.product_id == product_id)
    )
    if active_only:
        q = q.filter(ProductColor.activo.is_(True))
    return q.order_by(Color.sort_order.asc(), Color.label.asc()).all()


def product_requires_color(db: Session, product_id: int) -> bool:
    return (
        db.query(ProductColor)
        .filter(ProductColor.product_id == product_id, ProductColor.activo.is_(True))
        .count()
        > 0
    )


def sync_product_colors(db: Session, product_id: int, color_ids: List[int]) -> None:
    db.query(ProductColor).filter(ProductColor.product_id == product_id).delete(
        synchronize_session=False
    )
    if not color_ids:
        return
    rows = db.query(Color).filter(Color.color_id.in_(color_ids)).all()
    found = {c.color_id for c in rows}
    missing = [cid for cid in color_ids if cid not in found]
    if missing:
        raise HTTPException(status_code=400, detail=f"Colores no encontrados: {missing}")
    for cid in color_ids:
        db.add(ProductColor(product_id=product_id, color_id=cid, activo=True))


def create_color(db: Session, *, label: str, hex_value: Optional[str] = None) -> Color:
    label = (label or "").strip()
    if not label:
        raise HTTPException(status_code=400, detail="El nombre del color es obligatorio.")
    code = normalize_color_code(label)
    hex_clean = None
    if hex_value:
        h = hex_value.strip()
        if h and not h.startswith("#"):
            h = "#" + h
        if h and re.match(r"^#[0-9A-Fa-f]{6}$", h):
            hex_clean = h.upper()
    existing = db.query(Color).filter(Color.code == code).first()
    if existing:
        if hex_clean and not existing.hex:
            existing.hex = hex_clean
            db.flush()
        return existing
    max_order = db.query(Color.sort_order).order_by(Color.sort_order.desc()).limit(1).scalar()
    sort_order = (max_order or 0) + 10
    row = Color(code=code, label=label[:64], sort_order=sort_order, hex=hex_clean)
    db.add(row)
    db.flush()
    return row


def validate_line_color(db: Session, product_id: int, color_id: Optional[int]) -> Optional[Color]:
    requires = product_requires_color(db, product_id)
    if not requires:
        if color_id is not None:
            # Ignore stray color_id for products without colors configured.
            return None
        return None
    if not color_id:
        raise HTTPException(
            status_code=400,
            detail="Seleccioná un color para cada prenda que lo requiera.",
        )
    link = (
        db.query(Color)
        .join(ProductColor, ProductColor.color_id == Color.color_id)
        .filter(
            ProductColor.product_id == product_id,
            ProductColor.color_id == color_id,
            ProductColor.activo.is_(True),
        )
        .first()
    )
    if not link:
        raise HTTPException(status_code=400, detail="El color elegido no está disponible para este producto.")
    return link
