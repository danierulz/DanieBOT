"""Product variant matrix sync for admin and provider imports."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from database.models.ProductColor import ProductColor
from database.models.ProductVariant import ProductVariant
from database.models.Size import Size


def sync_product_variants(db: Session, product_id: int, items: list[dict[str, Any]]) -> None:
    db.query(ProductVariant).filter(ProductVariant.product_id == product_id).delete(
        synchronize_session=False
    )
    for item in items:
        code = (item.get("size_code") or "").strip().upper()
        if not code:
            continue
        size = db.query(Size).filter(Size.code == code).first()
        if not size:
            continue
        color_id_raw = item.get("color_id")
        color_id = int(color_id_raw) if color_id_raw not in (None, "") else None
        if color_id is not None:
            linked = (
                db.query(ProductColor)
                .filter(
                    ProductColor.product_id == product_id,
                    ProductColor.color_id == color_id,
                    ProductColor.activo.is_(True),
                )
                .first()
            )
            if not linked:
                continue
        qty = int(item.get("qty_stock_local", 0) or 0)
        enc = bool(item.get("encargo_habilitado", False))
        dias_raw = item.get("dias_encargo_estimados")
        dias_i = int(dias_raw) if dias_raw not in (None, "") else None
        if qty < 0:
            qty = 0
        matrix_cell = color_id is not None
        if qty == 0 and not enc and not matrix_cell:
            continue
        db.add(
            ProductVariant(
                product_id=product_id,
                size_id=size.size_id,
                color_id=color_id,
                qty_stock_local=qty,
                encargo_habilitado=enc,
                dias_encargo_estimados=dias_i,
                activo=True,
            )
        )
