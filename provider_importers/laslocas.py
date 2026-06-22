import json
import os
import re
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from provider_importers.types import ImportedProduct, ProviderImportError  # noqa: F401

__all__ = [
    "ImportedProduct",
    "ProviderImportError",
    "fetch_laslocas_product",
    "parse_laslocas_product",
]

LASLOCAS_HOSTS = {"laslocas.com", "www.laslocas.com"}
LOGIN_URL = "https://laslocas.com/login"
DEFAULT_TIMEOUT_SECONDS = 30
MAX_GALLERY_IMAGES = 24
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def fetch_laslocas_product(url: str) -> ImportedProduct:
    _validate_laslocas_url(url)
    session = _authenticated_session()
    try:
        response = session.get(url, timeout=DEFAULT_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ProviderImportError(f"No se pudo acceder a Las Locas: {exc}") from exc
    product = parse_laslocas_product(response.text, response.url)
    product.image_assets = _download_gallery_images(session, product.image_urls)
    product.image_urls = []
    return product


def parse_laslocas_product(html: str, source_url: str) -> ImportedProduct:
    _validate_laslocas_url(source_url)
    soup = BeautifulSoup(html, "html.parser")
    page_ficha = _page_ficha_from_url(source_url)

    cod_el = soup.select_one("#codProd")
    cod_product = _squash_ws(cod_el.get_text() if cod_el else "")
    if not cod_product:
        raise ProviderImportError("No se pudo detectar el codigo de producto Las Locas (#codProd).")

    title_el = soup.select_one("h1.item-title")
    item_title = _squash_ws(title_el.get_text() if title_el else "")
    if not item_title:
        raise ProviderImportError("No se pudo detectar el titulo del producto Las Locas.")

    json_product = _find_product_jsonld(soup)
    sku = _parse_int(json_product.get("sku"))
    description = _squash_ws(str(json_product.get("description") or ""))
    price = _parse_price_from_offers(json_product.get("offers"))
    if price is None:
        price = _extract_price_from_html(soup)
    if price is None:
        raise ProviderImportError("No se pudo detectar el precio del producto Las Locas.")

    image_urls = _extract_gallery_urls(soup, source_url)

    return ImportedProduct(
        provider="laslocas",
        source_url=source_url,
        title=item_title,
        description=description or f"Producto importado desde Las Locas ({cod_product}).",
        price=price,
        cod_product=cod_product[:50],
        sku=sku,
        image_urls=image_urls,
        page_ficha=page_ficha,
    )


def _build_login_payload(form, email: str, password: str) -> dict[str, str]:
    """El formulario usa name=_username/_password (ids inputEmail/inputPassword)."""
    payload: dict[str, str] = {}
    if not form:
        raise ProviderImportError("No se encontro el formulario de login en Las Locas.")

    for inp in form.find_all("input"):
        name = inp.get("name")
        if not name:
            continue
        field_type = (inp.get("type") or "").lower()
        field_id = inp.get("id") or ""

        if field_type == "email" or field_id == "inputEmail":
            payload[name] = email
        elif field_type == "password" or field_id == "inputPassword":
            payload[name] = password
        elif field_type == "hidden":
            payload[name] = inp.get("value") or ""
        elif field_type in ("text", ""):
            payload[name] = inp.get("value") or ""

    if "_username" not in payload:
        raise ProviderImportError("No se detecto el campo _username en el login Las Locas.")
    if "_password" not in payload:
        raise ProviderImportError("No se detecto el campo _password en el login Las Locas.")
    if "_csrf_token" not in payload:
        raise ProviderImportError("No se detecto token CSRF en el login Las Locas.")

    return payload


def _authenticated_session() -> requests.Session:
    email = os.getenv("LOGIN_EMAIL", "").strip()
    password = os.getenv("LOGIN_PASS", "").strip()
    if not email or not password:
        raise ProviderImportError(
            "Faltan LOGIN_EMAIL y LOGIN_PASS para importar productos de Las Locas."
        )

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-AR,es;q=0.9",
        }
    )
    try:
        login_page = session.get(LOGIN_URL, timeout=DEFAULT_TIMEOUT_SECONDS)
        login_page.raise_for_status()
    except requests.RequestException as exc:
        raise ProviderImportError(f"No se pudo abrir el login de Las Locas: {exc}") from exc

    soup = BeautifulSoup(login_page.text, "html.parser")
    form = soup.find("form")
    action = urljoin(LOGIN_URL, form.get("action") if form and form.get("action") else LOGIN_URL)
    payload = _build_login_payload(form, email, password)

    try:
        post = session.post(
            action,
            data=payload,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            allow_redirects=True,
            headers={"Referer": LOGIN_URL, "Origin": "https://laslocas.com"},
        )
        post.raise_for_status()
    except requests.RequestException as exc:
        raise ProviderImportError(f"No se pudo iniciar sesion en Las Locas: {exc}") from exc

    post_soup = BeautifulSoup(post.text, "html.parser")
    post_path = urlparse(post.url).path.rstrip("/")
    if post_path == "/login" or post_soup.select_one("form #inputEmail"):
        raise ProviderImportError("Credenciales de Las Locas invalidas o login rechazado.")
    return session


def _validate_laslocas_url(url: str) -> None:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in LASLOCAS_HOSTS:
        raise ProviderImportError("Solo se aceptan URLs de productos de laslocas.com.")
    if "/ficha" not in parsed.path:
        raise ProviderImportError("La URL de Las Locas debe apuntar a una ficha (/ficha-...).")


def _page_ficha_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    return path.replace("/", "") or "ficha"


def _loads_jsonld(raw: str) -> Any:
    """Parse JSON-LD; Las Locas sometimes embeds raw newlines inside strings."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return json.loads(raw, strict=False)


def _find_product_jsonld(soup: BeautifulSoup) -> dict[str, Any]:
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            parsed = _loads_jsonld(raw)
        except json.JSONDecodeError:
            continue
        items = parsed if isinstance(parsed, list) else [parsed]
        for item in items:
            if isinstance(item, dict) and item.get("@type") == "Product":
                return item
            if isinstance(item, dict) and item.get("@graph"):
                for node in item["@graph"]:
                    if isinstance(node, dict) and node.get("@type") == "Product":
                        return node
    return {}


def _parse_price_from_offers(offers: Any) -> Optional[int]:
    if isinstance(offers, dict):
        return _parse_money(offers.get("price"))
    if isinstance(offers, list):
        for offer in offers:
            if isinstance(offer, dict):
                price = _parse_money(offer.get("price"))
                if price is not None:
                    return price
    return None


def _extract_price_from_html(soup: BeautifulSoup) -> Optional[int]:
    for selector in ("[class*='price']", ".b2", ".item-price"):
        for element in soup.select(selector):
            price = _parse_money_from_text(element.get_text(" ", strip=True))
            if price is not None:
                return price
    return None


def _parse_money_from_text(text: str) -> Optional[int]:
    match = re.search(
        r"\$\s*(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)",
        str(text or ""),
    )
    if not match:
        return None
    return _parse_money(match.group(1))


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


def _parse_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    text = re.sub(r"\D+", "", str(value))
    return int(text) if text else None


def _extract_gallery_urls(soup: BeautifulSoup, source_url: str) -> list[str]:
    candidates: list[str] = []
    for selector in (
        "motion.div.d2 a[href]",
        "motion.d2 a[href]",
        "motion.div.d2 a[href]",
        "div.d2 a[href]",
        ".d2 a[href]",
    ):
        for el in soup.select(selector):
            href = el.get("href")
            if href:
                candidates.append(urljoin(source_url, href))
        if candidates:
            break
    return _dedupe_urls(candidates)[:MAX_GALLERY_IMAGES]


def _download_gallery_images(
    session: requests.Session, urls: list[str]
) -> list[tuple[str, bytes]]:
    assets: list[tuple[str, bytes]] = []
    for url in urls:
        try:
            resp = session.get(url, timeout=DEFAULT_TIMEOUT_SECONDS)
            resp.raise_for_status()
        except requests.RequestException:
            continue
        filename = urlparse(url).path.split("/")[-1] or f"image-{len(assets) + 1}.jpg"
        assets.append((filename, resp.content))
    if not assets and urls:
        raise ProviderImportError("No se pudieron descargar las imagenes de la ficha Las Locas.")
    return assets


def _dedupe_urls(urls: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for url in urls:
        key = url.lower()
        if key not in seen:
            seen.add(key)
            out.append(url)
    return out


def _squash_ws(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()
