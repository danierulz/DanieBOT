"""Discover product URLs from the HOLIC WooCommerce catalog."""
from __future__ import annotations

import re
import time
from typing import Callable
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from provider_importers.types import ProviderImportError
from provider_importers.bulk.delays import LISTING_PAGE_DELAY_SECONDS

HOLIC_CATALOG_URL = "https://holiclothing.com.ar/tienda/"
DEFAULT_TIMEOUT_SECONDS = 30
MAX_PAGES = 200
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_PRODUCT_PATH_RE = re.compile(r"^/product/[^/]+/?$")
HOLIC_HOSTS = {"holiclothing.com.ar", "www.holiclothing.com.ar"}


def discover_holic_product_urls(
    session: requests.Session | None = None,
    *,
    catalog_url: str = HOLIC_CATALOG_URL,
    on_progress: Callable[[str, int], None] | None = None,
) -> list[str]:
    http = session or requests.Session()
    http.headers.setdefault("User-Agent", USER_AGENT)
    http.headers.setdefault("Accept-Language", "es-AR,es;q=0.9")

    discovered: list[str] = []
    base = catalog_url.rstrip("/")

    for page_num in range(1, MAX_PAGES + 1):
        if page_num > 1:
            time.sleep(LISTING_PAGE_DELAY_SECONDS)
        listing_url = base + "/" if page_num == 1 else f"{base}/page/{page_num}/"
        try:
            response = http.get(listing_url, timeout=DEFAULT_TIMEOUT_SECONDS)
            response.raise_for_status()
        except requests.RequestException as exc:
            if page_num == 1:
                raise ProviderImportError(
                    f"No se pudo acceder al catálogo HOLIC ({listing_url}): {exc}"
                ) from exc
            break

        before_count = len(discovered)
        page_products = extract_product_urls_from_listing(response.text, response.url)
        for url in page_products:
            if url not in discovered:
                discovered.append(url)

        if on_progress:
            on_progress(f"HOLIC · listado · página {page_num}", len(discovered))

        if page_num > 1 and len(discovered) == before_count:
            break
        if page_num == 1 and not page_products:
            break

    return discovered


def extract_product_urls_from_listing(html: str, source_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []

    for anchor in soup.select("a[href]"):
        href = anchor.get("href")
        if not href:
            continue
        normalized = normalize_holic_product_url(href, source_url)
        if normalized:
            candidates.append(normalized)

    return _dedupe_preserve_order(candidates)


def normalize_holic_product_url(raw_url: str, base_url: str) -> str | None:
    absolute = urljoin(base_url, raw_url.strip())
    parsed = urlparse(absolute)
    if parsed.netloc.lower() not in HOLIC_HOSTS:
        return None
    if "add-to-cart" in parsed.path or "product-category" in parsed.path:
        return None
    if not _PRODUCT_PATH_RE.match(parsed.path):
        return None
    clean = parsed._replace(query="", fragment="")
    path = clean.path.rstrip("/") + "/"
    return urlunparse((clean.scheme, clean.netloc.lower(), path, "", "", ""))


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out
