"""Discover product URLs from Las Locas listing pages."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from provider_importers.laslocas import DEFAULT_TIMEOUT_SECONDS, _authenticated_session
from provider_importers.types import ProviderImportError
from provider_importers.bulk.delays import LISTING_PAGE_DELAY_SECONDS

LASLOCAS_BASE = "https://laslocas.com"
CATEGORIES_FILE = Path(__file__).with_name("laslocas_categories.json")


def load_laslocas_categories() -> list[dict[str, str]]:
    raw = json.loads(CATEGORIES_FILE.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ProviderImportError("laslocas_categories.json debe ser una lista.")
    return raw


def get_laslocas_category(category_id: str) -> dict[str, str]:
    for row in load_laslocas_categories():
        if row.get("id") == category_id:
            return row
    raise ProviderImportError(f"Categoría Las Locas desconocida: {category_id}")


def listing_url_for_category(
    category: dict[str, str],
    page: int = 1,
    *,
    ajax: bool = False,
) -> str:
    path = category["listing_path"].strip("/")
    base = f"{LASLOCAS_BASE}/{path}"
    page_n = max(int(page or 1), 1)
    if ajax:
        return f"{base}?page={page_n}&ajax=1"
    if page_n <= 1:
        return base
    return f"{base}?page={page_n}"


def discover_laslocas_product_urls(
    session: requests.Session | None = None,
    *,
    category_id: str | None = None,
    all_categories: bool = False,
    max_pages: int = 0,
    on_progress: Callable[[str, int], None] | None = None,
) -> list[str]:
    http = session or _authenticated_session()
    categories: list[dict[str, str]]
    if all_categories:
        categories = load_laslocas_categories()
    elif category_id:
        categories = [get_laslocas_category(category_id)]
    else:
        categories = [get_laslocas_category("denim")]

    discovered: list[str] = []
    for category in categories:
        category_urls = _discover_category_urls(
            http,
            category,
            max_pages=max_pages,
            on_progress=on_progress,
            total_so_far=len(discovered),
        )
        for url in category_urls:
            if url not in discovered:
                discovered.append(url)
    return discovered


def _discover_category_urls(
    session: requests.Session,
    category: dict[str, str],
    *,
    max_pages: int,
    on_progress: Callable[[str, int], None] | None = None,
    total_so_far: int = 0,
) -> list[str]:
    # El listado público ya no trae fichas en el HTML inicial: las carga
    # el infinite scroll vía ?page=N&ajax=1.
    page_limit = max_pages if max_pages and max_pages > 0 else 200
    urls: list[str] = []
    for page in range(1, page_limit + 1):
        if page > 1:
            time.sleep(LISTING_PAGE_DELAY_SECONDS)
        listing_url = listing_url_for_category(category, page=page, ajax=True)
        try:
            response = session.get(
                listing_url,
                timeout=DEFAULT_TIMEOUT_SECONDS,
                headers={"X-Requested-With": "XMLHttpRequest", "Accept": "*/*"},
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            if page == 1:
                raise ProviderImportError(
                    f"No se pudo acceder al listado Las Locas ({listing_url}): {exc}"
                ) from exc
            break
        html = response.text or ""
        if not html.strip():
            if page == 1:
                raise ProviderImportError(
                    f"El listado Las Locas no devolvió productos ({listing_url})."
                )
            break
        page_urls = extract_ficha_urls(html, response.url or listing_url)
        if not page_urls:
            if page == 1:
                raise ProviderImportError(
                    f"El listado Las Locas no devolvió fichas ({listing_url})."
                )
            break
        added = 0
        for url in page_urls:
            if url not in urls:
                urls.append(url)
                added += 1
        if on_progress:
            label = category.get("name") or category.get("id") or "categoría"
            on_progress(
                f"Las Locas · {label} · página {page}",
                total_so_far + len(urls),
            )
        if added == 0:
            break
    return urls


def extract_ficha_urls(html: str, source_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    for anchor in soup.select("a[href*='ficha']"):
        href = anchor.get("href") or ""
        absolute = urljoin(source_url, href)
        parsed = urlparse(absolute)
        if parsed.netloc.lower() not in {"laslocas.com", "www.laslocas.com"}:
            continue
        if "/ficha" not in parsed.path:
            continue
        clean = absolute.split("#")[0].split("?")[0]
        if clean not in urls:
            urls.append(clean)
    return urls
