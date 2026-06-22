import json
import re
import unicodedata
from html import unescape
from typing import Any, Iterable, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from provider_importers.types import ImportedProduct, ProviderImportError  # noqa: F401

__all__ = [
    "ImportedProduct",
    "ProviderImportError",
    "fetch_holic_product",
    "parse_holic_product",
]

HOLIC_HOSTS = {"holiclothing.com.ar", "www.holiclothing.com.ar"}
DEFAULT_TIMEOUT_SECONDS = 20
SKIP_CATEGORY_SLUGS = {"ver-todo", "sale", "new-in", "fire-sale", "fire-sale!!!"}


def fetch_holic_product(url: str) -> ImportedProduct:
    _validate_holic_url(url)
    try:
        response = requests.get(
            url,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                )
            },
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        body_snippet = ""
        if exc.response is not None:
            body_snippet = (exc.response.text or "")[:200].lower()
        if status == 429 or "too many request" in body_snippet:
            raise ProviderImportError(
                "HOLIC limitó las consultas (demasiados pedidos). "
                "Esperá unos minutos e intentá de nuevo.",
                code="rate_limit",
            ) from exc
        raise ProviderImportError(
            f"No se pudo acceder a HOLIC (HTTP {status}): {exc}",
            code="http_error",
        ) from exc
    except requests.RequestException as exc:
        raise ProviderImportError(
            f"No se pudo acceder a HOLIC: {exc}",
            code="network_error",
        ) from exc
    return parse_holic_product(response.text, response.url)


def parse_holic_product(html: str, source_url: str) -> ImportedProduct:
    _validate_holic_url(source_url)
    soup = BeautifulSoup(html, "html.parser")
    item_page_json = _find_item_page_jsonld(soup)

    title = _first_non_empty(
        _text(soup.select_one("h1.product_title")),
        _text(soup.select_one("h1")),
        _json_value(item_page_json, "name"),
    )
    if not title:
        raise ProviderImportError("No se pudo detectar el titulo del producto HOLIC.")

    description = _first_non_empty(
        _text(soup.select_one("#tab-description")),
        _meta_content(soup, "meta[name='description']"),
        _json_value(item_page_json, "description"),
    )

    sku_raw = _first_non_empty(
        _text(soup.select_one(".sku_wrapper .sku")),
        _text(soup.select_one(".product_meta .sku")),
        _text(soup.select_one(".sku")),
    )

    final_price, original_price = _extract_prices(soup, item_page_json)
    if final_price is None:
        raise ProviderImportError("No se pudo detectar el precio del producto HOLIC.")

    discount_percent = _discount_percent(original_price, final_price)
    image_urls = _extract_image_urls(soup, item_page_json, source_url)
    colors = _extract_woodmart_colors(soup)
    category_slug = _extract_category_slug(soup)
    slug = _slugify(urlparse(source_url).path.rstrip("/").split("/")[-1] or title)

    is_sale = bool(discount_percent and original_price)
    return ImportedProduct(
        provider="holic",
        source_url=source_url,
        title=_squash_ws(title),
        description=_squash_ws(description or ""),
        price=final_price,
        original_price=original_price,
        discount_percent=discount_percent,
        is_sale=is_sale,
        sku=None,
        cod_product=_build_cod_product(sku_raw, slug),
        image_urls=image_urls,
        category_slug=category_slug,
        colors=colors,
    )


def _validate_holic_url(url: str) -> None:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in HOLIC_HOSTS:
        raise ProviderImportError("Solo se aceptan URLs de productos de holiclothing.com.ar.")
    path = parsed.path.lower()
    if "/product/" not in path and "/producto/" not in path:
        raise ProviderImportError("La URL de HOLIC debe apuntar a un producto.")


def _find_item_page_jsonld(soup: BeautifulSoup) -> dict[str, Any]:
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for node in _walk_jsonld(parsed):
            types = node.get("@type") if isinstance(node, dict) else None
            if isinstance(types, str):
                types = [types]
            if isinstance(types, list) and "ItemPage" in types:
                return node
    return {}


def _walk_jsonld(node: Any) -> Iterable[dict[str, Any]]:
    if isinstance(node, dict):
        yield node
        for child in node.values():
            yield from _walk_jsonld(child)
    elif isinstance(node, list):
        for child in node:
            yield from _walk_jsonld(child)


def _extract_prices(soup: BeautifulSoup, item_page_json: dict[str, Any]) -> tuple[Optional[int], Optional[int]]:
    price_box = (
        soup.select_one(".summary p.price")
        or soup.select_one(".product-summary p.price")
        or soup.select_one("p.price")
    )
    final_price = _parse_money(_text(price_box.select_one("ins .amount")) if price_box else None)
    original_price = _parse_money(_text(price_box.select_one("del .amount")) if price_box else None)
    if final_price is None and price_box:
        amounts = [_parse_money(_text(x)) for x in price_box.select(".amount")]
        amounts = [x for x in amounts if x is not None]
        if amounts:
            final_price = amounts[-1]
            original_price = amounts[0] if len(amounts) > 1 else None

    if final_price is None:
        offer_prices = list(_iter_offer_prices(item_page_json.get("offers")))
        if offer_prices:
            final_price = offer_prices[-1]
            original_price = offer_prices[0] if len(offer_prices) > 1 else original_price

    if original_price == final_price:
        original_price = None
    return final_price, original_price


def _iter_offer_prices(offers: Any) -> Iterable[int]:
    offer_items = offers if isinstance(offers, list) else [offers]
    for offer in offer_items:
        if not isinstance(offer, dict):
            continue
        price = _parse_money(offer.get("price"))
        if price is not None:
            yield price
        specs = offer.get("priceSpecification")
        spec_items = specs if isinstance(specs, list) else [specs]
        for spec in spec_items:
            if isinstance(spec, dict):
                spec_price = _parse_money(spec.get("price"))
                if spec_price is not None:
                    yield spec_price


def _extract_image_urls(soup: BeautifulSoup, item_page_json: dict[str, Any], source_url: str) -> list[str]:
    candidates: list[str] = []
    image = item_page_json.get("image")
    if isinstance(image, dict):
        image_url = image.get("url")
        if isinstance(image_url, str):
            candidates.append(image_url)
    elif isinstance(image, str):
        candidates.append(image)

    for selector, attr in (
        (".woocommerce-product-gallery__image a[href]", "href"),
        (".woocommerce-product-gallery img[data-large_image]", "data-large_image"),
        ("meta[property='og:image']", "content"),
    ):
        for el in soup.select(selector):
            value = el.get(attr)
            if value:
                candidates.append(value)
    return _dedupe([urljoin(source_url, x) for x in candidates if x])


def _extract_woodmart_colors(soup: BeautifulSoup) -> list[str]:
    colors: list[str] = []
    skip_labels = {
        "color",
        "price",
        "stock",
        "sku",
        "precio",
        "cantidad",
        "elige una opción",
        "choose an option",
        "elegí",
        "limpiar",
    }

    for swatch in soup.select(".wd-swatches-product .wd-swatch, .wd-swatches .wd-swatch"):
        value = _first_non_empty(
            swatch.get("title"),
            swatch.get("aria-label"),
            swatch.get("data-value"),
        )
        if value and value.lower() not in skip_labels:
            colors.append(_squash_ws(value))

    for option in soup.select("select[name*='pa_color'] option, select[id*='pa_color'] option"):
        value = _squash_ws(_text(option))
        if value and value.lower() not in skip_labels:
            colors.append(value)

    return _dedupe(colors)


def _extract_category_slug(soup: BeautifulSoup) -> Optional[str]:
    for link in soup.select(".posted_in a[href], a[href*='/product-category/']"):
        parsed = urlparse(link.get("href") or "")
        parts = [p for p in parsed.path.split("/") if p]
        if "product-category" not in parts:
            continue
        slug = parts[-1].lower()
        if slug and slug not in SKIP_CATEGORY_SLUGS:
            return slug
    return None


def _build_cod_product(sku_raw: Optional[str], slug: str) -> str:
    sku_part = _slugify(str(sku_raw or "").strip()) or "sin-sku"
    code = f"holic-{sku_part}-{slug}"
    return code[:50].rstrip("-")


def _parse_money(value: Any) -> Optional[int]:
    if value is None:
        return None
    text = unescape(str(value))
    text = re.sub(r"[^\d,\.]", "", text)
    if not text:
        return None
    if "," in text and "." in text:
        if text.rfind(".") > text.rfind(","):
            text = text.replace(",", "")
        else:
            text = text.replace(".", "").replace(",", ".")
    elif "." in text:
        parts = text.split(".")
        if len(parts[-1]) == 3:
            text = "".join(parts)
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return int(round(float(text)))
    except ValueError:
        return None


def _discount_percent(original: Optional[int], final: int) -> Optional[int]:
    if not original or original <= final:
        return None
    return max(1, min(95, round((original - final) * 100 / original)))


def _json_value(data: dict[str, Any], key: str) -> Optional[str]:
    value = data.get(key) if isinstance(data, dict) else None
    return str(value) if value not in (None, "") else None


def _meta_content(soup: BeautifulSoup, selector: str) -> Optional[str]:
    meta = soup.select_one(selector)
    return meta.get("content") if meta else None


def _text(element: Any) -> str:
    if not element:
        return ""
    return element.get_text(" ", strip=True)


def _first_non_empty(*items: Optional[str]) -> Optional[str]:
    for item in items:
        if item and str(item).strip():
            return str(item).strip()
    return None


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        clean = _squash_ws(item)
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            out.append(clean)
    return out


def _squash_ws(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value.lower()).strip("-")
    return slug
