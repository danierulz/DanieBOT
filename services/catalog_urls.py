"""URLs del catálogo web con filtros de categoría y talle."""
from __future__ import annotations

import re
from urllib.parse import urlencode

from config import get_site_public_url

_SIZE_CODE_RE = re.compile(r"^[A-Z0-9]{1,32}$")


def _is_valid_size_code(code: str) -> bool:
    return bool(code and code != "ALL" and _SIZE_CODE_RE.match(code))


def build_catalog_url(
    cat_slug: str | None = None,
    size_code: str | None = None,
) -> str:
    """
    Arma la URL de la vitrina con query params que entiende index.html y /api/productos.

    - cat_slug: slug de categoría o "todos"; None/"" omite filtro de categoría.
    - size_code: código de talle (S, M, 38, …); None, "" o "ALL" omite filtro de talle.
    """
    params: dict[str, str] = {}
    slug = (cat_slug or "").strip().lower()
    if slug and slug != "todos":
        params["cat"] = slug
    elif slug == "todos":
        params["cat"] = "todos"

    code = (size_code or "").strip().upper()
    if _is_valid_size_code(code):
        params["size_code"] = code

    base = get_site_public_url()
    if not params:
        return f"{base}/"
    return f"{base}/?{urlencode(params)}"
