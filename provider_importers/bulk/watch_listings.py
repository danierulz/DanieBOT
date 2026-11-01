"""First-page listing cards for the local provider watch.

One HTTP GET per provider. No product-page fetch and no catalog walk.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from decimal import Decimal, ROUND_HALF_UP
from html import unescape
from typing import Callable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

from provider_importers.bulk.laslocas_catalog import (
    extract_ficha_urls,
    get_laslocas_category,
    listing_url_for_category,
)
from provider_importers.bulk.rate_limit import (
    RateLimitExceeded,
    RateLimitPolicy,
    call_with_rate_limit_backoff,
    response_is_rate_limited,
)
from provider_importers.holic import _build_cod_product as build_holic_cod
from provider_importers.holic_catalog import (
    HOLIC_CATALOG_URL,
    normalize_holic_product_url,
)
from provider_importers.laslocas import DEFAULT_TIMEOUT_SECONDS, _authenticated_session
from provider_importers.nissie import _build_cod_product as build_nissie_cod
from provider_importers.nissie_catalog import (
    NISSIE_CATALOG_URL,
    normalize_nissie_product_url,
)
from provider_importers.sochic import _build_cod_product as build_sochic_cod
from provider_importers.sochic_catalog import (
    SOCHIC_SHOP_URL,
    normalize_sochic_product_url,
)
from provider_importers.types import ProviderImportError

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
# One listing request. A 429 stops that provider; it does not retry in a loop.
WATCH_LISTING_POLICY = RateLimitPolicy(max_retries=0, hard_stop=True, initial_backoff_seconds=5)

_SKIP_TITLES = {
    "añadir al carrito",
    "agregar al carrito",
    "add to cart",
    "comprar",
    "ver",
    "ver más",
    "ver mas",
    "quick view",
    "sale",
}
_CARD_CLASSES = {
    "product",
    "type-product",
    "product-card",
    "js-item-product",
    "item-product",
}


class WatchListingError(Exception):
    """The first listing page could not be read. Safe to show in the admin UI."""


@dataclass(frozen=True)
class ListingHit:
    url: str
    title: str | None = None
    price: int | None = None
    cod_product: str | None = None


@dataclass(frozen=True)
class ListingPage:
    hits: tuple[ListingHit, ...]
    discovered: int


def parse_ars_amount(raw: str | None) -> int | None:
    """Parse an Argentine listing price (``$29.000`` or ``29000.50``) to int."""
    text = unescape(str(raw or "")).replace("\xa0", " ")
    match = re.search(r"\d[\d.,]*", text)
    if not match:
        return None
    token = match.group(0).strip(".,")
    if not token or not re.search(r"\d", token):
        return None
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", token):
        return int(token.replace(".", ""))
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+,\d{1,2}", token):
        whole, frac = token.split(",")
        return _half_up(f"{whole.replace('.', '')}.{frac}")
    if re.fullmatch(r"\d+,\d{1,2}", token):
        return _half_up(token.replace(",", "."))
    if re.fullmatch(r"\d+\.\d{1,2}", token):
        return _half_up(token)
    if re.fullmatch(r"\d+", token):
        return int(token)
    return None


def _half_up(number: str) -> int:
    return int(Decimal(number).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def fetch_provider_listing(
    provider: str,
    *,
    limit: int,
    laslocas_category: str,
    session: requests.Session | None = None,
) -> ListingPage:
    """Read the first listing page and keep the first ``limit`` cards."""
    if provider == "sochic":
        return _fetch_html_listing(
            session,
            SOCHIC_SHOP_URL,
            lambda html, page_url: extract_sochic_listing_hits(html, page_url),
            limit=limit,
            rate_limit=True,
        )
    if provider == "holic":
        return _fetch_html_listing(
            session,
            HOLIC_CATALOG_URL,
            lambda html, page_url: extract_holic_listing_hits(html, page_url),
            limit=limit,
            rate_limit=False,
        )
    if provider == "nissie":
        return _fetch_html_listing(
            session,
            NISSIE_CATALOG_URL,
            lambda html, page_url: extract_nissie_listing_hits(html, page_url),
            limit=limit,
            rate_limit=False,
        )
    if provider == "laslocas":
        return _fetch_laslocas(session, laslocas_category, limit)
    raise WatchListingError(f"Proveedor sin listado de novedades: {provider}")


def extract_sochic_listing_hits(html: str, source_url: str) -> list[ListingHit]:
    return _extract_hits(
        html,
        source_url,
        normalize_sochic_product_url,
        cod_for=_woo_cod(build_sochic_cod),
    )


def extract_holic_listing_hits(html: str, source_url: str) -> list[ListingHit]:
    return _extract_hits(
        html,
        source_url,
        normalize_holic_product_url,
        cod_for=_woo_cod(build_holic_cod),
    )


def extract_nissie_listing_hits(html: str, source_url: str) -> list[ListingHit]:
    soup = BeautifulSoup(html, "html.parser")
    hits = _extract_hits(
        html,
        source_url,
        normalize_nissie_product_url,
        cod_for=_nissie_cod_from_card,
        soup=soup,
    )
    return _apply_nissie_jsonld(soup, hits)


_LASLOCAS_PRODUCT_RE = re.compile(r"^/productos/[^/]+/?$")
_LASLOCAS_HOSTS = {"laslocas.com", "www.laslocas.com"}


def normalize_laslocas_listing_url(raw_url: str, base_url: str) -> str | None:
    """A ficha (legacy) or a storefront product (``/productos/<slug>/``)."""
    absolute = urljoin(base_url, (raw_url or "").strip())
    parsed = urlparse(absolute)
    if parsed.netloc.lower() not in _LASLOCAS_HOSTS:
        return None
    if "/ficha" in parsed.path:
        return absolute.split("#")[0].split("?")[0]
    if not _LASLOCAS_PRODUCT_RE.match(parsed.path):
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        return None
    path = "/" + "/".join(parts) + "/"
    return f"https://laslocas.com{path}"


def extract_laslocas_listing_hits(html: str, source_url: str) -> list[ListingHit]:
    """Titles and prices from the card. One row per ficha or storefront product."""
    soup = BeautifulSoup(html, "html.parser")
    hits: dict[str, ListingHit] = {}
    order: list[str] = []
    anchors = _listing_anchors(soup)
    for anchor in anchors:
        href = anchor.get("href") or ""
        clean = normalize_laslocas_listing_url(href, source_url)
        if not clean:
            continue
        card = _card_container(anchor)
        title = _title_from(anchor, card)
        price = _price_from(card)
        code = _laslocas_cod(card)
        if clean not in hits:
            order.append(clean)
            hits[clean] = ListingHit(url=clean, title=title, price=price, cod_product=code)
        else:
            hits[clean] = _fill(hits[clean], title=title, price=price, cod_product=code)
    if order:
        return [hits[url] for url in order]
    return [ListingHit(url=url) for url in extract_ficha_urls(html, source_url)]


def _listing_anchors(soup: BeautifulSoup) -> list[Tag]:
    """Prefer product cards so the nav and the footer do not lead the list."""
    cards = soup.select(".js-item-product, .item-product, li.product, article.product")
    anchors: list[Tag] = []
    for card in cards:
        anchors.extend(card.select("a[href]"))
    if anchors:
        return anchors
    return list(soup.select("a[href]"))


def _fetch_laslocas(
    session: requests.Session | None,
    category_id: str,
    limit: int,
) -> ListingPage:
    try:
        category = get_laslocas_category(category_id)
    except ProviderImportError as exc:
        raise WatchListingError(str(exc)) from exc
    http = session or _authenticated_session()
    listing_url = listing_url_for_category(category, page=1, ajax=True)
    try:
        response = http.get(
            listing_url,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            headers={"X-Requested-With": "XMLHttpRequest", "Accept": "*/*"},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise WatchListingError(
            f"No se pudo leer el listado de Las Locas ({listing_url})."
        ) from exc
    html = response.text or ""
    page_url = response.url or listing_url
    hits = extract_laslocas_listing_hits(html, page_url)
    return ListingPage(hits=tuple(hits[:limit]), discovered=len(hits))


def _fetch_html_listing(
    session: requests.Session | None,
    listing_url: str,
    extract: Callable[[str, str], list[ListingHit]],
    *,
    limit: int,
    rate_limit: bool,
) -> ListingPage:
    http = session or requests.Session()
    _assign_listing_headers(http)

    def once():
        response = http.get(listing_url, timeout=DEFAULT_TIMEOUT_SECONDS)
        if rate_limit and response_is_rate_limited(response):
            status = getattr(response, "status_code", None) or 429
            raise requests.HTTPError(f"HTTP {status} rate limit", response=response)
        response.raise_for_status()
        return response

    try:
        if rate_limit:
            response = call_with_rate_limit_backoff(
                once,
                WATCH_LISTING_POLICY,
                sleep=lambda _seconds: None,
            )
        else:
            response = once()
    except RateLimitExceeded as exc:
        minutes = max(int(WATCH_LISTING_POLICY.cooldown_hint_seconds // 60), 1)
        raise WatchListingError(
            "So Chic limitó las consultas en el listado. "
            "Se frenó esta marca: no se pidieron fichas de producto. "
            f"Esperá unos {minutes} minutos y volvé a buscar."
        ) from exc
    except requests.RequestException as exc:
        raise WatchListingError(f"No se pudo leer el listado ({listing_url}).") from exc

    page_url = getattr(response, "url", None) or listing_url
    hits = extract(response.text or "", page_url)
    return ListingPage(hits=tuple(hits[:limit]), discovered=len(hits))


def _extract_hits(
    html: str,
    source_url: str,
    normalize_url: Callable[[str, str], str | None],
    *,
    cod_for: Callable[[Tag, str], str | None] | None = None,
    soup: BeautifulSoup | None = None,
) -> list[ListingHit]:
    parsed = soup or BeautifulSoup(html, "html.parser")
    hits: dict[str, ListingHit] = {}
    order: list[str] = []
    for anchor in parsed.select("a[href]"):
        href = anchor.get("href")
        if not href:
            continue
        url = normalize_url(href, source_url)
        if not url:
            continue
        card = _card_container(anchor)
        title = _title_from(anchor, card)
        price = _price_from(card)
        code = cod_for(card, url) if cod_for else None
        if url not in hits:
            order.append(url)
            hits[url] = ListingHit(url=url, title=title, price=price, cod_product=code)
        else:
            hits[url] = _fill(hits[url], title=title, price=price, cod_product=code)
    return [hits[url] for url in order]


def _fill(
    prev: ListingHit,
    *,
    title: str | None,
    price: int | None,
    cod_product: str | None,
) -> ListingHit:
    return replace(
        prev,
        title=prev.title or title,
        price=prev.price if prev.price is not None else price,
        cod_product=prev.cod_product or cod_product,
    )


def _card_container(anchor: Tag) -> Tag:
    node: Tag = anchor
    fallback: Tag = anchor.parent if isinstance(anchor.parent, Tag) else anchor
    for _ in range(8):
        parent = node.parent if isinstance(node.parent, Tag) else None
        if parent is None or parent.name in {"body", "html", "[document]"}:
            break
        if _is_card(parent) or parent.name in {"li", "article"}:
            return parent
        node = parent
        fallback = parent
    return fallback


def _is_card(node: Tag) -> bool:
    classes = {str(item).lower() for item in (node.get("class") or [])}
    if classes & _CARD_CLASSES:
        return True
    return any(item.startswith("js-item") for item in classes)


def _title_from(anchor: Tag, card: Tag) -> str | None:
    for selector in (
        "h1",
        "h2",
        "h3",
        ".woocommerce-loop-product__title",
        ".js-item-name",
        ".item-name",
    ):
        node = anchor.select_one(selector) or card.select_one(selector)
        if node is None:
            continue
        text = _squash(node.get_text(" ", strip=True))
        if _usable_title(text):
            return text[:255]
    titled = _squash(str(anchor.get("title") or ""))
    if _usable_title(titled):
        return titled[:255]
    image = anchor.find("img")
    if isinstance(image, Tag):
        alt = _squash(str(image.get("alt") or ""))
        if _usable_title(alt):
            return alt[:255]
    text = _squash(anchor.get_text(" ", strip=True))
    if _usable_title(text) and len(text) <= 140 and "$" not in text:
        return text[:255]
    return None


def _usable_title(text: str) -> bool:
    if not text:
        return False
    return text.casefold() not in _SKIP_TITLES


def _price_from(card: Tag) -> int | None:
    ins = card.select_one("ins .amount, ins .woocommerce-Price-amount, ins .price, ins")
    if ins is not None:
        amount = parse_ars_amount(ins.get_text(" ", strip=True))
        if amount is not None:
            return amount
    for selector in (
        ".js-price-display",
        ".price .amount",
        ".woocommerce-Price-amount",
        ".price",
        ".precio",
        ".product-price",
        "[itemprop='price']",
    ):
        node = card.select_one(selector)
        if node is None:
            continue
        content = node.get("content")
        if content:
            amount = parse_ars_amount(str(content))
            if amount is not None:
                return amount
        amount = parse_ars_amount(node.get_text(" ", strip=True))
        if amount is not None:
            return amount
    return None


def _woo_cod(builder: Callable[..., str]) -> Callable[[Tag, str], str | None]:
    def cod_for(card: Tag, url: str) -> str | None:
        sku = _sku_from_card(card)
        if not sku:
            return None
        slug = _slug_from_url(url)
        if not slug:
            return None
        code = builder(sku, slug)
        return code or None

    return cod_for


def _sku_from_card(card: Tag) -> str | None:
    for node in card.select("[data-sku], [data-product_sku], .sku"):
        raw = node.get("data-sku") or node.get("data-product_sku") or node.get_text(" ", strip=True)
        text = _squash(str(raw or ""))
        if text and text.casefold() not in {"sku", "n/a"}:
            return text[:80]
    return None


def _nissie_cod_from_card(card: Tag, url: str) -> str | None:
    del url
    node: Tag | None = card
    for _ in range(6):
        if node is None:
            break
        raw = str(node.get("data-product-id") or "").strip()
        if raw.isdigit():
            return build_nissie_cod(raw, "")
        parent = node.parent if isinstance(node.parent, Tag) else None
        node = parent
    return None


def _laslocas_cod(card: Tag) -> str | None:
    for node in card.select("[data-cod], [data-codigo], .codProd, #codProd, .codigo"):
        raw = node.get("data-cod") or node.get("data-codigo") or node.get_text(" ", strip=True)
        text = re.sub(r"\s+", "", str(raw or ""))
        if text and len(text) <= 50 and re.fullmatch(r"[A-Za-z0-9_-]+", text):
            return text
    return None


def _slug_from_url(url: str) -> str:
    parts = [part for part in urlparse(url).path.split("/") if part]
    return parts[-1] if parts else ""


def _apply_nissie_jsonld(soup: BeautifulSoup, hits: list[ListingHit]) -> list[ListingHit]:
    by_url = {hit.url: hit for hit in hits}
    for node in _jsonld_nodes(soup):
        group = node.get("productGroupID") or node.get("productGroupId")
        url_value = node.get("url") if isinstance(node.get("url"), str) else ""
        if not url_value:
            main_entity = node.get("mainEntityOfPage")
            if isinstance(main_entity, dict) and isinstance(main_entity.get("@id"), str):
                url_value = main_entity["@id"]
        if not url_value and isinstance(node.get("@id"), str) and "/productos/" in node["@id"]:
            url_value = node["@id"]
        normalized = normalize_nissie_product_url(url_value, url_value) if url_value else None
        if not normalized or normalized not in by_url:
            continue
        prev = by_url[normalized]
        code = build_nissie_cod(str(group), "") if group else prev.cod_product
        title = prev.title
        if not title and isinstance(node.get("name"), str):
            candidate = _squash(node["name"])
            if _usable_title(candidate):
                title = candidate[:255]
        price = prev.price
        if price is None:
            price = _jsonld_price(node.get("offers"))
        by_url[normalized] = replace(prev, title=title, price=price, cod_product=code)
    return [by_url[hit.url] for hit in hits]


def _jsonld_price(offers: object) -> int | None:
    if isinstance(offers, dict):
        return parse_ars_amount(str(offers.get("price") or ""))
    if isinstance(offers, list):
        for offer in offers:
            if isinstance(offer, dict):
                amount = parse_ars_amount(str(offer.get("price") or ""))
                if amount is not None:
                    return amount
    return None


def _jsonld_nodes(soup: BeautifulSoup) -> list[dict]:
    nodes: list[dict] = []
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw, strict=False)
        except json.JSONDecodeError:
            continue
        _walk_json(parsed, nodes)
    return nodes


def _walk_json(value: object, nodes: list[dict]) -> None:
    if isinstance(value, dict):
        nodes.append(value)
        for child in value.values():
            _walk_json(child, nodes)
    elif isinstance(value, list):
        for child in value:
            _walk_json(child, nodes)


def _assign_listing_headers(http) -> None:
    """Overwrite the Session default ``python-requests`` agent.

    ``setdefault`` leaves that agent in place, and Nissie (Tienda Nube)
    answers 403. Product pages are not requested from here.
    """
    headers = getattr(http, "headers", None)
    if headers is None or not hasattr(headers, "__setitem__"):
        return
    headers["User-Agent"] = USER_AGENT
    accept = ""
    getter = getattr(headers, "get", None)
    if callable(getter):
        accept = str(getter("Accept") or "")
    if not accept or accept == "*/*":
        headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    if callable(getter) and not getter("Accept-Language"):
        headers["Accept-Language"] = "es-AR,es;q=0.9"


def _squash(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()
