import re
import unicodedata
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from config import DEFAULT_SIZE_GROUP
from database.models.Category import Category
from database.models.Products import Products
from services.sizes import validate_size_group


def normalize_category_slug(name: str, *, explicit: Optional[str] = None) -> str:
    if explicit is not None and str(explicit).strip():
        slug = str(explicit).strip().lower()
        slug = re.sub(r"[^a-z0-9-]+", "-", slug).strip("-")
    else:
        raw = (name or "").strip()
        if not raw:
            raise HTTPException(status_code=400, detail="El nombre de la categoría es obligatorio.")
        normalized = unicodedata.normalize("NFKD", raw)
        ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")
        if not slug:
            slug = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
    if not slug:
        raise HTTPException(status_code=400, detail="No se pudo generar un slug para la categoría.")
    if len(slug) > 64:
        raise HTTPException(status_code=400, detail="El slug es demasiado largo (máx. 64 caracteres).")
    return slug


def category_to_public(c: Category, *, product_count: Optional[int] = None) -> dict:
    data = {
        "category_id": c.category_id,
        "slug": c.slug,
        "name": c.name,
        "sort_order": c.sort_order,
        "size_group": c.size_group if c.size_group in ("letter", "numeric") else DEFAULT_SIZE_GROUP,
        "activo": bool(c.activo),
    }
    if product_count is not None:
        data["product_count"] = product_count
    return data


def list_categories_public(db: Session) -> List[dict]:
    rows = (
        db.query(Category)
        .filter(Category.activo.is_(True))
        .order_by(Category.sort_order.asc(), Category.name.asc())
        .all()
    )
    return [category_to_public(c) for c in rows]


def list_categories_for_nav(db: Session) -> List[dict]:
    rows = (
        db.query(Category)
        .filter(Category.activo.is_(True))
        .order_by(Category.sort_order.asc(), Category.name.asc())
        .all()
    )
    return [{"name": c.name, "slug": c.slug} for c in rows]


def list_categories_admin(db: Session) -> List[dict]:
    from sqlalchemy import func

    rows = db.query(Category).order_by(Category.sort_order.asc(), Category.name.asc()).all()
    counts = dict(
        db.query(Products.category_id, func.count(Products.product_id))
        .filter(Products.category_id.isnot(None))
        .group_by(Products.category_id)
        .all()
    )
    return [category_to_public(c, product_count=counts.get(c.category_id, 0)) for c in rows]


def create_category(
    db: Session,
    *,
    name: str,
    slug: Optional[str] = None,
    size_group: str = DEFAULT_SIZE_GROUP,
    sort_order: Optional[int] = None,
    activo: bool = True,
) -> Category:
    clean_name = (name or "").strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="El nombre de la categoría es obligatorio.")
    clean_slug = normalize_category_slug(clean_name, explicit=slug)
    existing = db.query(Category).filter(Category.slug == clean_slug).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f'Ya existe la categoría "{existing.name}" ({existing.slug}). Editá la existente.',
        )
    group = validate_size_group(size_group)
    if sort_order is None:
        max_order = db.query(Category.sort_order).order_by(Category.sort_order.desc()).limit(1).scalar()
        sort_order = (max_order or 0) + 10
    row = Category(
        slug=clean_slug,
        name=clean_name[:120],
        sort_order=int(sort_order),
        size_group=group,
        activo=bool(activo),
    )
    db.add(row)
    db.flush()
    return row


def update_category(
    db: Session,
    category_id: int,
    *,
    name: Optional[str] = None,
    size_group: Optional[str] = None,
    sort_order: Optional[int] = None,
    activo: Optional[bool] = None,
) -> Category:
    row = db.query(Category).filter(Category.category_id == category_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Categoría no encontrada.")
    if name is not None:
        clean_name = name.strip()
        if not clean_name:
            raise HTTPException(status_code=400, detail="El nombre de la categoría es obligatorio.")
        row.name = clean_name[:120]
    if size_group is not None:
        row.size_group = validate_size_group(size_group)
    if sort_order is not None:
        row.sort_order = int(sort_order)
    if activo is not None:
        row.activo = bool(activo)
    db.flush()
    return row


def delete_category(db: Session, category_id: int) -> None:
    row = db.query(Category).filter(Category.category_id == category_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Categoría no encontrada.")
    usage = db.query(Products).filter(Products.category_id == category_id).count()
    if usage > 0:
        noun = "producto" if usage == 1 else "productos"
        raise HTTPException(
            status_code=409,
            detail=(
                f"Esta categoría tiene {usage} {noun} asignados. "
                "Reasignalos o desactivá la categoría en lugar de eliminarla."
            ),
        )
    db.delete(row)
    db.flush()
