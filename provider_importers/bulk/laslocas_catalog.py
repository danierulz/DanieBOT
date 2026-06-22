"""Discover product URLs from Las Locas listing pages."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from provider_importers.laslocas import DEFAULT_TIMEOUT_SECONDS, _authenticated_session
from provider_importers.types import ProviderImportError
from provider_importers.bulk.delays import LISTING_PAGE_DELAY_SECONDS

LASLOCAS_BASE = "https://laslocas.com"
CATEGORIES_FILE = Path(__file__).with_name("laslocas_categories.json")
_PAGE_NUMBER_RE = re.compile(r"page=(\d+)")


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


def listing_url_for_category(category: dict[str, str], page: int = 1) -> str:
    path = category["listing_path"].strip("/")
    base = f"{LASLOCAS_BASE}/{path}"
    if page <= 1:
        return base
    return f"{base}?page={page}"


def discover_laslocas_product_urls(
    session: requests.Session | None = None,
    *,
    category_id: str | None = None,
    all_categories: bool = False,
    max_pages: int = 0,
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
        category_urls = _discover_category_urls(http, category, max_pages=max_pages)
        for url in category_urls:
            if url not in discovered:
                discovered.append(url)
    return discovered


def _discover_category_urls(
    session: requests.Session,
    category: dict[str, str],
    *,
    max_pages: int,
) -> list[str]:
    first_url = listing_url_for_category(category, page=1)
    try:
        first_response = session.get(first_url, timeout=DEFAULT_TIMEOUT_SECONDS)
        first_response.raise_for_status()
    except requests.RequestException as exc:
        raise ProviderImportError(
            f"No se pudo acceder al listado Las Locas ({first_url}): {exc}"
        ) from exc

    page_limit = _resolve_page_limit(first_response.text, max_pages)
    urls: list[str] = []
    for page in range(1, page_limit + 1):
        if page > 1:
            time.sleep(LISTING_PAGE_DELAY_SECONDS)
        listing_url = listing_url_for_category(category, page=page)
        if page == 1:
            html, base_url = first_response.text, first_response.url
        else:
            try:
                response = session.get(listing_url, timeout=DEFAULT_TIMEOUT_SECONDS)
                response.raise_for_status()
            except requests.RequestException:
                break
            html, base_url = response.text, response.url
        page_urls = extract_ficha_urls(html, base_url)
        for url in page_urls:
            if url not in urls:
                urls.append(url)
    return urls


def _resolve_page_limit(html: str, max_pages: int) -> int:
    soup = BeautifulSoup(html, "html.parser")
    pag = soup.select_one("#pag")
    highest = 1
    if pag:
        for anchor in pag.select("a[href*='page']"):
            href = anchor.get("href") or ""
            match = _PAGE_NUMBER_RE.search(href)
            if match:
                highest = max(highest, int(match.group(1)))
    if max_pages and max_pages > 0:
        return min(highest, max_pages)
    return highest


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
