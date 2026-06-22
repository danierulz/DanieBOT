import json
import re
import unicodedata
from typing import Any, Iterable, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from provider_importers.types import ImportedProduct, ProviderImportError  # noqa: F401

__all__ = [
    "ImportedProduct",
    "ProviderImportError",
    "fetch_nissie_product",
    "parse_nissie_product",
]

NISSIE_HOSTS = {"nissiedenim.com.ar", "www.nissiedenim.com.ar"}
DEFAULT_TIMEOUT_SECONDS = 30
MAX_GALLERY_IMAGES = 24
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def fetch_nissie_product(url: str) -> ImportedProduct:
    _validate_nissie_url(url)
    try:
        response = requests.get(
            url,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "es-AR,es;q=0.9",
            },
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ProviderImportError(f"No se pudo acceder a Nissie Denim: {exc}") from exc
    return parse_nissie_product(response.text, response.url)


def parse_nissie_product(html: str, source_url: str) -> ImportedProduct:
    _validate_nissie_url(source_url)
    soup = BeautifulSoup(html, "html.parser")
    product_group = _find_product_group_jsonld(soup)
    slug = _slugify(urlparse(source_url).path.rstrip("/").split("/")[-1] or "")

    title = _first_non_empty(
        _json_value(product_group, "name"),
        _text(soup.select_one("h1")),
    )
    if not title:
        raise ProviderImportError("No se pudo detectar el titulo del producto Nissie.")

    description = _first_non_empty(
        _json_value(product_group, "description"),
        _meta_content(soup, "meta[name='description']"),
        _text(soup.select_one(".product-description, .product-description-content")),
    )

    group_id_raw = _first_non_empty(
        _json_value(product_group, "productGroupID"),
        _json_value(product_group, "sku"),
    )
    sku = _parse_int(group_id_raw)
    variants = product_group.get("hasVariant") if isinstance(product_group, dict) else None
    if not isinstance(variants, list):
        variants = []

    price = _price_from_variants(variants)
    if price is None:
        price = _extract_price_from_html(soup)
    if price is None:
        raise ProviderImportError("No se pudo detectar el precio del producto Nissie.")

    colors = _extract_colors_from_variants(variants)
    image_urls = _extract_image_urls(soup, product_group, source_url)
    category_slug = _extract_category_slug(product_group, soup)

    return ImportedProduct(
        provider="nissie",
        source_url=source_url,
        title=_squash_ws(title),
        description=_squash_ws(description or ""),
        price=price,
        sku=sku,
        cod_product=_build_cod_product(group_id_raw, slug),
        image_urls=image_urls,
        category_slug=category_slug,
        colors=colors,
    )


def _validate_nissie_url(url: str) -> None:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in NISSIE_HOSTS:
        raise ProviderImportError("Solo se aceptan URLs de productos de nissiedenim.com.ar.")
    if "/productos/" not in parsed.path:
        raise ProviderImportError("La URL de Nissie debe apuntar a un producto (/productos/...).")


def _find_product_group_jsonld(soup: BeautifulSoup) -> dict[str, Any]:
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text()
        if not raw:
            continue
        for block in _split_jsonld_blocks(raw):
            try:
                parsed = json.loads(block)
            except json.JSONDecodeError:
                try:
                    parsed = json.loads(block, strict=False)
                except json.JSONDecodeError:
                    continue
            for node in _walk_jsonld(parsed):
                node_type = node.get("@type")
                if node_type == "ProductGroup":
                    return node
                if node_type == "WebPage":
                    main_entity = node.get("mainEntity")
                    if isinstance(main_entity, dict) and main_entity.get("@type") == "ProductGroup":
                        return main_entity
                if node_type == "Product":
                    return node
    return {}


def _split_jsonld_blocks(raw: str) -> list[str]:
    blocks: list[str] = []
    depth = 0
    start: Optional[int] = None
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
    if not blocks:
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


def _price_from_variants(variants: list[Any]) -> Optional[int]:
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        offers = variant.get("offers")
        if isinstance(offers, dict):
            price = _parse_money(offers.get("price"))
            if price is not None:
                return price
    return None


def _extract_colors_from_variants(variants: list[Any]) -> list[str]:
    colors: list[str] = []
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        color = _squash_ws(str(variant.get("color") or ""))
        if color:
            colors.append(color)
    return _dedupe(colors)


def _extract_price_from_html(soup: BeautifulSoup) -> Optional[int]:
    for selector in (
        ".js-price-display",
        ".price",
        ".product-price",
        "[data-component='product.price']",
        "h1",
    ):
        for element in soup.select(selector):
            price = _parse_money_from_text(element.get_text(" ", strip=True))
            if price is not None:
                return price
    return None


def _extract_image_urls(
    soup: BeautifulSoup,
    product_group: dict[str, Any],
    source_url: str,
) -> list[str]:
    candidates: list[str] = []
    for value in _as_list(product_group.get("image")):
        if isinstance(value, dict):
            value = value.get("url")
        if isinstance(value, str):
            candidates.append(value)

    for selector in (
        ".js-product-slide img",
        ".product-slider img",
        ".swiper-slide img",
        "meta[property='og:image']",
    ):
        for element in soup.select(selector):
            if selector.startswith("meta"):
                value = element.get("content")
            else:
                value = element.get("src") or element.get("data-src")
            if value:
                candidates.append(value)

    for element in soup.select("img[src*='mitiendanube.com/stores'][src*='/products/']"):
        value = element.get("src")
        if value and "themes/common/logo" not in value:
            candidates.append(value)

    normalized = [_normalize_image_url(source_url, url) for url in candidates if url]
    return _dedupe(normalized)[:MAX_GALLERY_IMAGES]


def _normalize_image_url(source_url: str, image_url: str) -> str:
    absolute = urljoin(source_url, image_url)
    absolute = re.sub(r"-240-0\.(webp|jpg|jpeg|png)", r"-640-0.\1", absolute, flags=re.I)
    absolute = re.sub(r"-480-0\.(webp|jpg|jpeg|png)", r"-640-0.\1", absolute, flags=re.I)
    return absolute


def _extract_category_slug(product_group: dict[str, Any], soup: BeautifulSoup) -> Optional[str]:
    breadcrumb = product_group.get("breadcrumb")
    if isinstance(breadcrumb, dict):
        slug = _slug_from_breadcrumb(breadcrumb.get("itemListElement"))
        if slug:
            return slug

    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text()
        if not raw:
            continue
        for block in _split_jsonld_blocks(raw):
            try:
                parsed = json.loads(block, strict=False)
            except json.JSONDecodeError:
                continue
            for node in _walk_jsonld(parsed):
                if node.get("@type") != "WebPage":
                    continue
                breadcrumb = node.get("breadcrumb")
                if isinstance(breadcrumb, dict):
                    slug = _slug_from_breadcrumb(breadcrumb.get("itemListElement"))
                    if slug:
                        return slug
    return None


def _slug_from_breadcrumb(items: Any) -> Optional[str]:
    if not isinstance(items, list):
        return None
    category_items = []
    for item in items:
        if not isinstance(item, dict):
            continue
        item_url = str(item.get("item") or "")
        if "/productos/" in item_url:
            continue
        category_items.append(item)
    if not category_items:
        return None
    last = category_items[-1]
    parsed = urlparse(str(last.get("item") or ""))
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        return None
    return parts[-1].lower()


def _build_cod_product(group_id_raw: Optional[str], slug: str) -> str:
    del slug
    id_part = _slugify(str(group_id_raw or "").strip()) or "sin-id"
    return f"nissie-{id_part}"[:50].rstrip("-")


def _parse_money(value: Any) -> Optional[int]:
    if value is None:
        return None
    text = re.sub(r"[^\d,\.]", "", str(value))
    if not text:
        return None
    try:
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", text):
            return int(text.replace(".", ""))
        if "," in text and "." in text:
            text = text.replace(".", "").replace(",", ".")
        elif "," in text:
            text = text.replace(",", ".")
        return int(round(float(text)))
    except ValueError:
        return None


def _parse_money_from_text(text: str) -> Optional[int]:
    match = re.search(
        r"\$\s*(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)",
        str(text or ""),
    )
    if not match:
        return None
    return _parse_money(match.group(1))


def _parse_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    text = re.sub(r"\D+", "", str(value))
    return int(text) if text else None


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


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


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
