"""Shelf-price markup for the notebook bulk CLI.

Applied after a product page is fetched and before persist. A percent of 0
leaves the scraped amounts unchanged.
"""

from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP

from provider_importers.types import ImportedProduct


def apply_price_markup(product: ImportedProduct, percent: float) -> ImportedProduct:
    """Multiply ``price`` and ``original_price`` (when set) by ``1 + percent/100``.

    Amounts round half away from zero to an int. ``discount_percent`` stays
    as scraped, because both prices move by the same factor. Mutates and
    returns ``product``.
    """
    if isinstance(percent, bool) or not isinstance(percent, (int, float)):
        raise ValueError("price_markup_percent debe ser un número")
    if not math.isfinite(percent):
        raise ValueError("price_markup_percent debe ser finito")
    if percent == 0:
        return product
    product.price = _marked_amount(product.price, percent)
    if product.original_price is not None:
        product.original_price = _marked_amount(product.original_price, percent)
    return product


def _marked_amount(amount: int, percent: float) -> int:
    factor = Decimal(1) + (Decimal(str(percent)) / Decimal(100))
    marked = Decimal(amount) * factor
    return int(marked.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
