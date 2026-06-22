import re
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from config import DEFAULT_SIZE_GROUP
from database.models.Category import Category
from database.models.ProductVariant import ProductVariant
from database.models.Size import Size

VALID_SIZE_GROUPS = frozenset({"letter", "numeric"})


def normalize_size_code(code: str) -> str:
    raw = (code or "").strip().upper()
    if not raw:
        raise HTTPException(status_code=400, detail="El código de talle es obligatorio.")
    if len(raw) > 32:
        raise HTTPException(status_code=400, detail="El código de talle es demasiado largo.")
    return raw


def infer_size_group(code: str) -> str:
    return "numeric" if re.fullmatch(r"\d{2,3}", (code or "").strip()) else "letter"


def validate_size_group(group: str) -> str:
    g = (group or "").strip().lower()
    if g not in VALID_SIZE_GROUPS:
        raise HTTPException(status_code=400, detail="El tipo de talle debe ser letter o numeric.")
    return g


def size_to_public(s: Size) -> dict:
    return {
        "size_id": s.size_id,
        "code": s.code,
        "label": s.label,
        "sort_order": s.sort_order,
        "size_group": s.size_group or DEFAULT_SIZE_GROUP,
    }


def get_size_group_for_category(db: Session, category_slug: str | None) -> str:
    if not category_slug or str(category_slug).strip().lower() in ("", "todos"):
        return DEFAULT_SIZE_GROUP
    slug = str(category_slug).strip().lower()
    row = db.query(Category).filter(Category.slug == slug, Category.activo.is_(True)).first()
    if row and row.size_group in VALID_SIZE_GROUPS:
        return row.size_group
    return DEFAULT_SIZE_GROUP


def get_size_codes_for_category(db: Session, category_slug: str | None) -> List[str]:
    group = get_size_group_for_category(db, category_slug)
    rows = (
        db.query(Size)
        .filter(Size.size_group == group)
        .order_by(Size.sort_order.asc(), Size.code.asc())
        .all()
    )
    return [s.code for s in rows]


def list_sizes_public(db: Session, category_slug: str | None = None) -> List[dict]:
    q = db.query(Size).order_by(Size.sort_order.asc(), Size.code.asc())
    if category_slug is not None and str(category_slug).strip():
        group = get_size_group_for_category(db, category_slug)
        q = q.filter(Size.size_group == group)
    return [size_to_public(s) for s in q.all()]


def list_all_sizes_admin(db: Session) -> List[dict]:
    rows = db.query(Size).order_by(Size.sort_order.asc(), Size.code.asc()).all()
    return [size_to_public(s) for s in rows]


def create_size(
    db: Session,
    *,
    code: str,
    label: str,
    size_group: str,
    sort_order: Optional[int] = None,
) -> Size:
    clean_code = normalize_size_code(code)
    clean_label = (label or "").strip()
    if not clean_label:
        raise HTTPException(status_code=400, detail="La etiqueta del talle es obligatoria.")
    group = validate_size_group(size_group)
    existing = db.query(Size).filter(Size.code == clean_code).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f'Ya existe el talle "{existing.label}" ({existing.code}). Editá el existente en la pestaña Talles.',
        )
    if sort_order is None:
        max_order = db.query(Size.sort_order).order_by(Size.sort_order.desc()).limit(1).scalar()
        sort_order = (max_order or 0) + 10
    row = Size(
        code=clean_code,
        label=clean_label[:64],
        sort_order=int(sort_order),
        size_group=group,
    )
    db.add(row)
    db.flush()
    return row


def update_size(
    db: Session,
    size_id: int,
    *,
    label: Optional[str] = None,
    size_group: Optional[str] = None,
    sort_order: Optional[int] = None,
) -> Size:
    row = db.query(Size).filter(Size.size_id == size_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Talle no encontrado.")
    if label is not None:
        clean_label = label.strip()
        if not clean_label:
            raise HTTPException(status_code=400, detail="La etiqueta del talle es obligatoria.")
        row.label = clean_label[:64]
    if size_group is not None:
        row.size_group = validate_size_group(size_group)
    if sort_order is not None:
        row.sort_order = int(sort_order)
    db.flush()
    return row


def delete_size(db: Session, size_id: int) -> None:
    row = db.query(Size).filter(Size.size_id == size_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Talle no encontrado.")
    usage = db.query(ProductVariant).filter(ProductVariant.size_id == size_id).count()
    if usage > 0:
        noun = "producto" if usage == 1 else "productos"
        raise HTTPException(
            status_code=409,
            detail=(
                f"Este talle está en {usage} {noun}. "
                "Quitá las variantes en esos productos antes de eliminarlo."
            ),
        )
    db.delete(row)
    db.flush()


def get_or_create_size_code(db: Session, size_code: str) -> str:
    """Usado por imports de proveedores: crea talle si no existe."""
    code = normalize_size_code(size_code or "UNICO")
    size = db.query(Size).filter(Size.code == code).first()
    if not size:
        group = infer_size_group(code)
        max_order = db.query(Size.sort_order).order_by(Size.sort_order.desc()).limit(1).scalar()
        db.add(
            Size(
                code=code,
                label="Único" if code == "UNICO" else code,
                sort_order=70 if code == "UNICO" else ((max_order or 0) + 10),
                size_group=group,
            )
        )
        db.flush()
    return code
