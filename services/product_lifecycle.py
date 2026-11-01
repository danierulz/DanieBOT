"""Product visibility lifecycle: draft vs active vs retired."""

from __future__ import annotations

from typing import Any, Optional

LIFECYCLE_DRAFT = "draft"
LIFECYCLE_ACTIVE = "active"
LIFECYCLE_RETIRED = "retired"
LIFECYCLES = frozenset({LIFECYCLE_DRAFT, LIFECYCLE_ACTIVE, LIFECYCLE_RETIRED})

LABELS_ES = {
    LIFECYCLE_DRAFT: "Pendiente",
    LIFECYCLE_ACTIVE: "En web",
    LIFECYCLE_RETIRED: "Baja",
}


def normalize_lifecycle(value: Any) -> Optional[str]:
    raw = str(value or "").strip().lower()
    if raw in LIFECYCLES:
        return raw
    return None


def lifecycle_of(product: Any) -> str:
    """Resolve lifecycle; fall back to legacy boolean status."""
    current = normalize_lifecycle(getattr(product, "lifecycle", None))
    if current:
        return current
    return LIFECYCLE_ACTIVE if bool(getattr(product, "status", False)) else LIFECYCLE_DRAFT


def apply_lifecycle(product: Any, lifecycle: str) -> str:
    value = normalize_lifecycle(lifecycle)
    if value is None:
        raise ValueError(f"lifecycle invalido: {lifecycle}")
    product.lifecycle = value
    product.status = value == LIFECYCLE_ACTIVE
    return value


def apply_status_bool(product: Any, want_active: bool) -> str:
    """Map the admin activo checkbox onto lifecycle.

    - Checking activo -> active
    - Unchecking while active -> retired (deliberate baja)
    - Unchecking while draft/retired -> leave draft/retired
    """
    if want_active:
        return apply_lifecycle(product, LIFECYCLE_ACTIVE)
    current = lifecycle_of(product)
    if current == LIFECYCLE_ACTIVE:
        return apply_lifecycle(product, LIFECYCLE_RETIRED)
    return apply_lifecycle(product, current or LIFECYCLE_DRAFT)


def lifecycle_label(value: Any) -> str:
    key = normalize_lifecycle(value) or LIFECYCLE_DRAFT
    return LABELS_ES.get(key, key)
