"""Cálculo de precios de catálogo (lista / sale). Fuente única para API y pedidos."""


def compute_pricing(price: int | None, is_sale: bool, discount_percent: int | None) -> dict:
    """Devuelve precio_original, precio_final, descuento_porcentaje y is_sale efectivo."""
    base = int(price) if price is not None else 0
    pct = int(discount_percent) if (is_sale and discount_percent and discount_percent > 0) else 0
    if pct > 95:
        pct = 95
    final = base
    on_sale_effective = False
    if pct > 0 and base > 0:
        final = int(round(base * (100 - pct) / 100))
        on_sale_effective = True
    return {
        "precio_original": base,
        "precio_final": final,
        "descuento_porcentaje": pct,
        "is_sale": on_sale_effective,
    }


def unit_price_for_product(product) -> float:
    """Precio unitario autorizado para un producto (con sale aplicado)."""
    p = compute_pricing(product.price, bool(product.is_sale), product.discount_percent)
    return float(p["precio_final"])
