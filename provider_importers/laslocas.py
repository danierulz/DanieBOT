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
    storefront = _is_laslocas_storefront_product_path(urlparse(source_url).path)

    json_product = _find_product_jsonld(soup)

    if storefront:
        title_el = soup.select_one("h1.js-product-name, h1[data-store^='product-name']")
        item_title = _squash_ws(title_el.get_text() if title_el else "")
        if not item_title:
            item_title = _squash_ws(str(json_product.get("name") or ""))
        if not item_title:
            raise ProviderImportError("No se pudo detectar el titulo del producto Las Locas.")

        cod_product = _storefront_cod_product(soup, source_url, json_product)
        sku = _parse_int(json_product.get("sku")) or _parse_int(cod_product)
        description = _squash_ws(str(json_product.get("description") or ""))
        price = _parse_price_from_offers(json_product.get("offers"))
        if price is None:
            price = _extract_price_from_html(soup)
        if price is None:
            raise ProviderImportError("No se pudo detectar el precio del producto Las Locas.")
        image_urls = _extract_gallery_urls(soup, source_url)
        if not image_urls:
            image_urls = _storefront_image_urls(soup, source_url, json_product)
    else:
        cod_el = soup.select_one("#codProd")
        cod_product = _squash_ws(cod_el.get_text() if cod_el else "")
        if not cod_product:
            raise ProviderImportError(
                "No se pudo detectar el codigo de producto Las Locas (#codProd)."
            )

        title_el = soup.select_one("h1.item-title")
        item_title = _squash_ws(title_el.get_text() if title_el else "")
        if not item_title:
            raise ProviderImportError("No se pudo detectar el titulo del producto Las Locas.")

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


def _storefront_cod_product(soup: BeautifulSoup, source_url: str, json_product: dict[str, Any]) -> str:
    form = soup.select_one("#product_form")
    if form is not None:
        add = form.find("input", attrs={"name": "add_to_cart"})
        if add and add.get("value"):
            return _squash_ws(str(add.get("value")))[:50]
        data_store = str(form.get("data-store") or "")
        m = re.search(r"product-form-(\d+)", data_store)
        if m:
            return m.group(1)[:50]
    h1 = soup.select_one("h1.js-product-name")
    if h1 is not None:
        data_store = str(h1.get("data-store") or "")
        m = re.search(r"product-name-(\d+)", data_store)
        if m:
            return m.group(1)[:50]
    for key in ("sku", "productID", "mpn"):
        value = _squash_ws(str(json_product.get(key) or ""))
        if value:
            return value[:50]
    slug = urlparse(source_url).path.strip("/").split("/")[-1]
    if slug:
        return slug[:50]
    raise ProviderImportError("No se pudo detectar el codigo del producto Las Locas.")


def _storefront_image_urls(
    soup: BeautifulSoup, source_url: str, json_product: dict[str, Any]
) -> list[str]:
    candidates: list[str] = []
    image = json_product.get("image")
    if isinstance(image, str):
        candidates.append(image)
    elif isinstance(image, list):
        for item in image:
            if isinstance(item, str):
                candidates.append(item)
            elif isinstance(item, dict) and isinstance(item.get("url"), str):
                candidates.append(item["url"])
    for img in soup.select("img[src], img[data-src]"):
        src = img.get("src") or img.get("data-src") or ""
        if "/products/" in src or "mitiendanube.com/stores" in src:
            if "empty-placeholder" in src or "/themes/" in src:
                continue
            candidates.append(src)
    absolute = [urljoin(source_url, u) if u.startswith("//") or u.startswith("/") else u for u in candidates]
    absolute = [("https:" + u) if u.startswith("//") else u for u in absolute]
    return _dedupe_urls(absolute)[:MAX_GALLERY_IMAGES]


def find_login_form(soup: BeautifulSoup):
    """The login form, not the search or newsletter form that appears first.

    Legacy pages use ``#inputEmail``. The storefront uses ``#login-form``.
    """
    if soup is None:
        return None
    form = soup.select_one("#login-form")
    if form is not None:
        return form
    form = soup.select_one("form[data-store='account-login']")
    if form is not None:
        return form
    for candidate in soup.find_all("form"):
        if candidate.select_one("#inputPassword, #inputEmail, input[type='password']"):
            return candidate
    return soup.find("form")


def _input_name(inp) -> str:
    return str(inp.get("name") or "").strip()


def _is_username_input(inp) -> bool:
    field_type = (inp.get("type") or "").lower()
    field_id = (inp.get("id") or "").lower()
    name = _input_name(inp).lower()
    if field_type == "hidden" or field_type in {"submit", "button", "checkbox", "radio"}:
        return False
    if field_type == "email" or field_id in {"inputemail", "email"}:
        return True
    return name in {"_username", "username", "email"} and field_type in {"text", ""}


def _is_password_input(inp) -> bool:
    field_type = (inp.get("type") or "").lower()
    field_id = (inp.get("id") or "").lower()
    name = _input_name(inp).lower()
    if field_type == "password" or field_id == "inputpassword":
        return True
    return name in {"_password", "password"} and field_type in {"text", ""}


def _build_login_payload(form, email: str, password: str) -> dict[str, str]:
    """Fill the username and password inputs by type, id, or name.

    Legacy Symfony posts ``_username`` / ``_password`` / ``_csrf_token``.
    The current storefront posts ``email`` / ``password`` and has no CSRF input.
    """
    payload: dict[str, str] = {}
    if not form:
        raise ProviderImportError("No se encontro el formulario de login en Las Locas.")

    saw_username = False
    saw_password = False
    requires_csrf = False
    for inp in form.find_all("input"):
        name = _input_name(inp)
        if not name:
            continue
        field_type = (inp.get("type") or "").lower()
        if name == "_csrf_token" or name == "_username":
            requires_csrf = True
        if _is_username_input(inp):
            payload[name] = email
            saw_username = True
        elif _is_password_input(inp):
            payload[name] = password
            saw_password = True
        elif field_type == "hidden":
            payload[name] = inp.get("value") or ""
        elif field_type in ("text", "") and name not in payload:
            payload[name] = inp.get("value") or ""

    if not saw_username:
        raise ProviderImportError("No se detecto el campo _username en el login Las Locas.")
    if not saw_password:
        raise ProviderImportError("No se detecto el campo _password en el login Las Locas.")
    if requires_csrf and "_csrf_token" not in payload:
        raise ProviderImportError("No se detecto token CSRF en el login Las Locas.")

    return payload


def _login_was_rejected(post: requests.Response) -> bool:
    path = urlparse(post.url).path.rstrip("/").lower()
    if path in {"/login", "/account/login"}:
        return True
    post_soup = BeautifulSoup(post.text or "", "html.parser")
    return post_soup.select_one("form #inputEmail, #login-form") is not None


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
    form = find_login_form(soup)
    action_attr = form.get("action") if form is not None else None
    action = urljoin(login_page.url or LOGIN_URL, action_attr or "")
    payload = _build_login_payload(form, email, password)

    try:
        post = session.post(
            action,
            data=payload,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            allow_redirects=True,
            headers={"Referer": login_page.url or LOGIN_URL, "Origin": "https://laslocas.com"},
        )
        post.raise_for_status()
    except requests.RequestException as exc:
        raise ProviderImportError(f"No se pudo iniciar sesion en Las Locas: {exc}") from exc

    if _login_was_rejected(post):
        raise ProviderImportError("Credenciales de Las Locas invalidas o login rechazado.")
    return session


_LASLOCAS_STOREFRONT_PRODUCT_RE = re.compile(r"^/productos/[^/]+/?$")


def _is_laslocas_ficha_path(path: str) -> bool:
    return "/ficha" in (path or "")


def _is_laslocas_storefront_product_path(path: str) -> bool:
    return bool(_LASLOCAS_STOREFRONT_PRODUCT_RE.match(path or ""))


def _validate_laslocas_url(url: str) -> None:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in LASLOCAS_HOSTS:
        raise ProviderImportError("Solo se aceptan URLs de productos de laslocas.com.")
    path = parsed.path or ""
    if not (_is_laslocas_ficha_path(path) or _is_laslocas_storefront_product_path(path)):
        raise ProviderImportError(
            "La URL de Las Locas debe apuntar a una ficha (/ficha-...) "
            "o a un producto de tienda (/productos/<slug>/)."
        )


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
            if not isinstance(item, dict):
                continue
            if item.get("@type") == "Product":
                return item
            main_entity = item.get("mainEntity")
            if isinstance(main_entity, dict) and main_entity.get("@type") == "Product":
                return main_entity
            graph = item.get("@graph")
            if isinstance(graph, list):
                for node in graph:
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
