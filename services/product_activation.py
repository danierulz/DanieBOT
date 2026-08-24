"""Rules for publishing a product as active in the storefront."""

from __future__ import annotations

from typing import Any, Iterable, Optional

NEED_CATEGORY = "Elegí una categoría."
NEED_PRICE = "Indicá un precio mayor a 0."
NEED_STOCK = "Cargá al menos un talle con unidades en local o por encargo."


def _as_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def variant_is_sellable(variant: Any) -> bool:
    if variant is None:
        return False
    if isinstance(variant, dict):
        qty = int(variant.get("qty_stock_local") or 0)
        encargo = bool(variant.get("encargo_habilitado"))
        activo = variant.get("activo", True)
        return bool(activo) and (qty > 0 or encargo)
    if not getattr(variant, "activo", True):
        return False
    qty = int(getattr(variant, "qty_stock_local", 0) or 0)
    encargo = bool(getattr(variant, "encargo_habilitado", False))
    return qty > 0 or encargo


def activation_blockers(
    *,
    category_id: Any,
    price: Any,
    variants: Optional[Iterable[Any]] = None,
) -> list[str]:
    """Return why a product cannot be published as active. Empty = ok."""
    blockers: list[str] = []
    if _as_int(category_id) is None or _as_int(category_id) <= 0:
        blockers.append(NEED_CATEGORY)
    price_i = _as_int(price)
    if price_i is None or price_i <= 0:
        blockers.append(NEED_PRICE)
    rows = list(variants or [])
    if not any(variant_is_sellable(v) for v in rows):
        blockers.append(NEED_STOCK)
    return blockers


def format_activation_error(blockers: list[str]) -> str:
    if not blockers:
        return ""
    return "No se puede activar: " + " ".join(blockers)
