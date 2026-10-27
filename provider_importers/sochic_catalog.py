"""Discover product URLs from the So Chic WooCommerce catalog.

Pagination matches WooCommerce (``/shop/`` and ``/shop/page/N/``), the same
shape HOLIC uses. Listing pauses reuse ``LISTING_PAGE_DELAY_SECONDS``.
"""

from __future__ import annotations

import re
import time
from typing import Callable
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from provider_importers.bulk.delays import LISTING_PAGE_DELAY_SECONDS
from provider_importers.bulk.rate_limit import (
    DEFAULT_RATE_LIMIT_POLICY,
    RateLimitExceeded,
    RateLimitPolicy,
    call_with_rate_limit_backoff,
    response_is_rate_limited,
)
from provider_importers.types import ProviderImportError

SOCHIC_SHOP_URL = "https://sochic.com.ar/shop/"
SOCHIC_HOSTS = {"sochic.com.ar", "www.sochic.com.ar"}
CANONICAL_HOST = "sochic.com.ar"
DEFAULT_TIMEOUT_SECONDS = 30
MAX_PAGES = 200
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_PRODUCT_PATH_RE = re.compile(r"^/product/[^/]+/?$")
_CATEGORY_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def discover_sochic_product_urls(
    session: requests.Session | None = None,
    *,
    catalog_url: str | None = None,
    category_slug: str | None = None,
    max_pages: int = 0,
    on_progress: Callable[[str, int], None] | None = None,
    rate_limit_policy: RateLimitPolicy | None = None,
    sleep: Callable[[float], None] | None = None,
) -> list[str]:
    """Walk the shop (or one product-category) and return ``/product/`` URLs.

    ``max_pages`` <= 0 walks until the listing ends, capped at ``MAX_PAGES``.
    HTTP 429 (or a rate-limit body) waits with ``rate_limit_policy`` and, if
    the budget runs out, raises ``RateLimitExceeded`` with the URLs already
    collected. Those URLs are not fetched in the same wave.
    """
    http = session or requests.Session()
    http.headers.setdefault("User-Agent", USER_AGENT)
    http.headers.setdefault("Accept-Language", "es-AR,es;q=0.9")
    policy = rate_limit_policy or DEFAULT_RATE_LIMIT_POLICY
    pause = sleep or time.sleep

    base = _catalog_base(catalog_url=catalog_url, category_slug=category_slug)
    page_cap = MAX_PAGES if not max_pages or max_pages <= 0 else min(int(max_pages), MAX_PAGES)
    discovered: list[str] = []

    for page_num in range(1, page_cap + 1):
        if page_num > 1:
            pause(LISTING_PAGE_DELAY_SECONDS)
        listing_url = _listing_page_url(base, page_num)
        try:
            response = _fetch_listing(http, listing_url, policy, pause)
        except RateLimitExceeded as exc:
            raise RateLimitExceeded(
                "So Chic limitó las consultas en el listado "
                f"({listing_url}). Se frenó la corrida para no seguir pegándole al sitio.",
                attempts=exc.attempts,
                policy=policy,
                partial_urls=list(discovered),
                where="listing",
            ) from exc
        except requests.RequestException as exc:
            if page_num == 1:
                raise ProviderImportError(
                    f"No se pudo acceder al catálogo So Chic ({listing_url}): {exc}"
                ) from exc
            break

        before_count = len(discovered)
        page_products = extract_product_urls_from_listing(response.text, response.url or listing_url)
        for url in page_products:
            if url not in discovered:
                discovered.append(url)

        if on_progress:
            on_progress(f"So Chic · listado · página {page_num}", len(discovered))

        if page_num > 1 and len(discovered) == before_count:
            break
        if page_num == 1 and not page_products:
            break

    return discovered


def _fetch_listing(http: requests.Session, listing_url: str, policy: RateLimitPolicy, pause):
    """GET one listing page. Rate limits sleep inside the backoff helper."""

    def once():
        response = http.get(listing_url, timeout=DEFAULT_TIMEOUT_SECONDS)
        if response_is_rate_limited(response):
            status = getattr(response, "status_code", None) or 429
            raise requests.HTTPError(f"HTTP {status} rate limit", response=response)
        response.raise_for_status()
        return response

    return call_with_rate_limit_backoff(once, policy, sleep=pause)


def extract_product_urls_from_listing(html: str, source_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []
    for anchor in soup.select("a[href]"):
        href = anchor.get("href")
        if not href:
            continue
        normalized = normalize_sochic_product_url(href, source_url)
        if normalized:
            candidates.append(normalized)
    return _dedupe_preserve_order(candidates)


def normalize_sochic_product_url(raw_url: str, base_url: str) -> str | None:
    absolute = urljoin(base_url, raw_url.strip())
    parsed = urlparse(absolute)
    if parsed.netloc.lower() not in SOCHIC_HOSTS:
        return None
    if "product-category" in parsed.path or parsed.path.rstrip("/") in {"/shop", "/product"}:
        return None
    if not _PRODUCT_PATH_RE.match(parsed.path):
        return None
    clean = parsed._replace(scheme="https", netloc=CANONICAL_HOST, query="", fragment="")
    path = clean.path.rstrip("/") + "/"
    return urlunparse((clean.scheme, clean.netloc, path, "", "", ""))


def _catalog_base(*, catalog_url: str | None, category_slug: str | None) -> str:
    if catalog_url:
        return catalog_url if catalog_url.endswith("/") else catalog_url + "/"
    slug = (category_slug or "").strip().strip("/")
    if not slug:
        return SOCHIC_SHOP_URL
    if not _CATEGORY_SLUG_RE.match(slug.lower()):
        raise ProviderImportError(
            "Categoría So Chic inválida. Usá el slug de /product-category/<slug>/ "
            "(por ejemplo camperas)."
        )
    return f"https://sochic.com.ar/product-category/{slug.lower()}/"


def _listing_page_url(base: str, page_num: int) -> str:
    root = base.rstrip("/") + "/"
    if page_num <= 1:
        return root
    return f"{root}page/{page_num}/"


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out
