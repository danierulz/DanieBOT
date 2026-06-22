"""Persistencia compartida de productos importados desde proveedores."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from config import PRODUCT_DESCRIPTION_MAX_LEN, PRODUCT_ITEM_TITLE_MAX_LEN
from database.models.Category import Category
from database.models.Color import Color
from database.models.ProductImages import ProductImages
from database.models.Products import Products
from provider_importers.types import ImportedProduct
from services.colors import get_or_create_color, normalize_color_code, sync_product_colors
from services.sizes import get_or_create_size_code


class ByteUploader(Protocol):
    def upload_bytes(self, blob_path: str, data: bytes) -> str: ...


@dataclass
class ProviderImportPayload:
    url: str = ""
    category_id: Optional[int] = None
    size_code: str = "UNICO"
    encargo_habilitado: bool = True
    dias_encargo_estimados: Optional[int] = None
    status: bool = False


ProviderImportOptions = ProviderImportPayload


def truncate(value: Optional[str], max_len: int) -> str:
    clean = " ".join(str(value or "").split())
    return clean[:max_len].rstrip()


def provider_description(product: ImportedProduct) -> str:
    parts: list[str] = []
    if product.description:
        parts.append(product.description)
    if product.colors:
        parts.append("Colores proveedor: " + ", ".join(product.colors))
    default = {
        "sochic": "Producto importado desde So Chic.",
        "laslocas": "Producto importado desde Las Locas.",
        "nissie": "Producto importado desde Nissie Denim.",
        "holic": "Producto importado desde HOLIC.",
    }
    return truncate(
        " | ".join(parts) or default.get(product.provider, "Producto importado."),
        PRODUCT_DESCRIPTION_MAX_LEN,
    )


def image_filename_from_url(image_url: str, idx: int, provider: str = "sochic") -> str:
    filename = os.path.basename(urlparse(image_url).path)
    return truncate(filename or f"{provider}-{idx + 1}.jpg", 255)


def page_ficha_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    return path.replace("/", "") or "ficha"


def product_is_active(product: Products) -> bool:
    return bool(product.status)


def resolve_category_id(db: Session, category_id_raw: Optional[int]) -> Optional[int]:
    if not category_id_raw or category_id_raw <= 0:
        return None
    exists = db.query(Category.category_id).filter(Category.category_id == category_id_raw).first()
    return category_id_raw if exists else None


def resolve_category_slug(db: Session, slug: Optional[str]) -> Optional[int]:
    if not slug:
        return None
    row = (
        db.query(Category.category_id)
        .filter(Category.slug == slug.strip().lower(), Category.activo.is_(True))
        .first()
    )
    return row[0] if row else None


def match_import_color_ids(db: Session, color_names: list[str]) -> list[int]:
    if not color_names:
        return []
    ids: list[int] = []
    for name in color_names:
        label = (name or "").strip()
        if not label:
            continue
        code = normalize_color_code(label)
        row = db.query(Color).filter(Color.code == code).first()
        if not row:
            row = get_or_create_color(db, label=label)
        if row.color_id not in ids:
            ids.append(row.color_id)
    return ids


def persist_imported_product(
    db: Session,
    imported: ImportedProduct,
    payload: ProviderImportPayload,
    uploader: ByteUploader,
    *,
    sync_variants_fn: Callable[[Session, int, list[dict[str, Any]]], None],
    match_color_ids_fn: Callable[[Session, list[str]], list[int]],
) -> dict:
    existing = db.query(Products).filter(Products.cod_product == imported.cod_product).first()
    if existing:
        return {
            "ok": True,
            "created": False,
            "id": existing.product_id,
            "provider": imported.provider,
            "cod_product": existing.cod_product,
            "activo": product_is_active(existing),
        }

    is_sale = imported.is_sale or bool(imported.discount_percent and imported.original_price)
    base_price = imported.original_price if is_sale else imported.price
    category_id = (
        resolve_category_id(db, payload.category_id)
        if payload.category_id
        else resolve_category_slug(db, imported.category_slug)
    )
    nuevo = Products(
        item_title=truncate(imported.title, PRODUCT_ITEM_TITLE_MAX_LEN),
        price=base_price,
        cod_product=imported.cod_product,
        name=truncate(imported.title, 80),
        sku=imported.sku,
        description=provider_description(imported),
        category_id=category_id,
        status=bool(payload.status),
        is_sale=is_sale,
        discount_percent=imported.discount_percent if is_sale else None,
        provider=imported.provider,
    )
    db.add(nuevo)
    db.flush()

    image_count = 0
    page_ficha = imported.page_ficha or page_ficha_from_url(imported.source_url)

    for idx, image_url in enumerate(imported.image_urls):
        db.add(
            ProductImages(
                product_id=nuevo.product_id,
                filename=image_filename_from_url(image_url, idx, imported.provider),
                url=image_url,
                is_main=(image_count == 0),
            )
        )
        image_count += 1

    for filename, data in imported.image_assets:
        blob_path = f"images/{page_ficha}/{filename}"
        public_url = uploader.upload_bytes(blob_path, data)
        db.add(
            ProductImages(
                product_id=nuevo.product_id,
                filename=truncate(filename, 255),
                url=public_url,
                is_main=(image_count == 0),
            )
        )
        image_count += 1

    size_code = get_or_create_size_code(db, payload.size_code)
    sync_variants_fn(
        db,
        nuevo.product_id,
        [
            {
                "size_code": size_code,
                "qty_stock_local": 0,
                "encargo_habilitado": payload.encargo_habilitado,
                "dias_encargo_estimados": payload.dias_encargo_estimados,
            }
        ],
    )
    import_color_ids = match_color_ids_fn(db, imported.colors)
    if import_color_ids:
        sync_product_colors(db, nuevo.product_id, import_color_ids)
    db.commit()
    db.refresh(nuevo)
    return {
        "ok": True,
        "created": True,
        "id": nuevo.product_id,
        "provider": imported.provider,
        "cod_product": nuevo.cod_product,
        "imagenes": image_count,
        "colores": imported.colors,
        "activo": product_is_active(nuevo),
    }
