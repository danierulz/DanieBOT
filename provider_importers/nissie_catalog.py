"""Discover product URLs from the Nissie Denim TiendaNube catalog."""
from __future__ import annotations

import json
import re
import time
from typing import Any, Callable, Iterable
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from provider_importers.types import ProviderImportError
from provider_importers.bulk.delays import LISTING_PAGE_DELAY_SECONDS

NISSIE_CATALOG_URL = "https://nissiedenim.com.ar/productos/"
DEFAULT_TIMEOUT_SECONDS = 30
MAX_PAGES = 200
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_PRODUCT_PATH_RE = re.compile(r"^/productos/[^/]+/?$")


def discover_nissie_product_urls(
    session: requests.Session | None = None,
    *,
    catalog_url: str = NISSIE_CATALOG_URL,
    on_progress: Callable[[str, int], None] | None = None,
) -> list[str]:
    http = session or requests.Session()
    http.headers.setdefault("User-Agent", USER_AGENT)
    http.headers.setdefault("Accept-Language", "es-AR,es;q=0.9")

    discovered: list[str] = []
    seen_pages: set[str] = set()
    page_urls = [catalog_url.rstrip("/") + "/"]
    page_index = 0

    while page_index < len(page_urls) and page_index < MAX_PAGES:
        listing_url = page_urls[page_index]
        page_index += 1
        if listing_url in seen_pages:
            continue
        seen_pages.add(listing_url)

        if len(seen_pages) > 1:
            time.sleep(LISTING_PAGE_DELAY_SECONDS)

        try:
            response = http.get(listing_url, timeout=DEFAULT_TIMEOUT_SECONDS)
            response.raise_for_status()
        except requests.RequestException as exc:
            if page_index == 1:
                raise ProviderImportError(
                    f"No se pudo acceder al catálogo Nissie ({listing_url}): {exc}"
                ) from exc
            continue

        before_count = len(discovered)
        page_products = extract_product_urls_from_listing(response.text, response.url)
        for url in page_products:
            if url not in discovered:
                discovered.append(url)

        if on_progress:
            on_progress(f"Nissie · listado · página {page_index}", len(discovered))

        for next_page in _extract_pagination_links(response.text, response.url):
            if next_page not in seen_pages and next_page not in page_urls:
                page_urls.append(next_page)

        if page_index == 1:
            page_num = 2
            while page_num <= MAX_PAGES:
                paged_url = f"{catalog_url.rstrip('/')}/?page={page_num}"
                if paged_url in seen_pages:
                    page_num += 1
                    continue
                seen_pages.add(paged_url)
                time.sleep(LISTING_PAGE_DELAY_SECONDS)
                try:
                    paged_resp = http.get(paged_url, timeout=DEFAULT_TIMEOUT_SECONDS)
                    if paged_resp.status_code >= 400:
                        break
                    paged_products = extract_product_urls_from_listing(
                        paged_resp.text, paged_resp.url
                    )
                    if not paged_products:
                        break
                    added = 0
                    for url in paged_products:
                        if url not in discovered:
                            discovered.append(url)
                            added += 1
                    if added == 0:
                        break
                    if on_progress:
                        on_progress(f"Nissie · listado · página {page_num}", len(discovered))
                except requests.RequestException:
                    break
                page_num += 1

        if page_index > 1 and len(discovered) == before_count and not page_products:
            continue

    return discovered


def extract_product_urls_from_listing(html: str, source_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []

    for anchor in soup.select("a[href]"):
        href = anchor.get("href")
        if not href:
            continue
        normalized = normalize_nissie_product_url(href, source_url)
        if normalized:
            candidates.append(normalized)

    for url in _extract_product_urls_from_jsonld(soup):
        candidates.append(url)

    return _dedupe_preserve_order(candidates)


def normalize_nissie_product_url(raw_url: str, base_url: str) -> str | None:
    absolute = urljoin(base_url, raw_url.strip())
    parsed = urlparse(absolute)
    if parsed.netloc.lower() not in {"nissiedenim.com.ar", "www.nissiedenim.com.ar"}:
        return None
    if not _PRODUCT_PATH_RE.match(parsed.path):
        return None
    clean = parsed._replace(query="", fragment="")
    path = clean.path.rstrip("/") + "/"
    return urlunparse((clean.scheme, clean.netloc.lower(), path, "", "", ""))


def _extract_pagination_links(html: str, source_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    pages: list[str] = []
    for anchor in soup.select("a[href]"):
        href = anchor.get("href") or ""
        absolute = urljoin(source_url, href)
        parsed = urlparse(absolute)
        if parsed.netloc.lower() not in {"nissiedenim.com.ar", "www.nissiedenim.com.ar"}:
            continue
        if "/productos/" not in parsed.path:
            continue
        if parsed.path.rstrip("/") == "/productos":
            continue
        if "page=" in parsed.query or re.search(r"/productos/page/\d+", parsed.path):
            pages.append(absolute.split("#")[0])
    return _dedupe_preserve_order(pages)


def _extract_product_urls_from_jsonld(soup: BeautifulSoup) -> list[str]:
    urls: list[str] = []
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text() or ""
        for block in _split_jsonld_blocks(raw):
            try:
                parsed = json.loads(block, strict=False)
            except json.JSONDecodeError:
                continue
            for node in _walk_jsonld(parsed):
                for key in ("@id", "url"):
                    value = node.get(key)
                    if isinstance(value, str) and "/productos/" in value:
                        normalized = normalize_nissie_product_url(value, value)
                        if normalized:
                            urls.append(normalized)
                main_entity = node.get("mainEntityOfPage")
                if isinstance(main_entity, dict):
                    page_id = main_entity.get("@id")
                    if isinstance(page_id, str):
                        normalized = normalize_nissie_product_url(page_id, page_id)
                        if normalized:
                            urls.append(normalized)
    return urls


def _split_jsonld_blocks(raw: str) -> list[str]:
    blocks: list[str] = []
    depth = 0
    start: int | None = None
    for index, char in enumerate(raw):
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start is not None:
                blocks.append(raw[start : index + 1])
                start = None
    if not blocks and raw.strip():
        blocks.append(raw.strip())
    return blocks


def _walk_jsonld(node: Any) -> Iterable[dict[str, Any]]:
    if isinstance(node, dict):
        yield node
        for child in node.values():
            yield from _walk_jsonld(child)
    elif isinstance(node, list):
        for child in node:
            yield from _walk_jsonld(child)


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out
