"""Export DanieBOT products to the JSON manifest robotRZ Graph scripts read.

Notebook only. This module reads Products and ProductImages and writes a UTF-8
JSON array. It does not call Meta Graph, scrape providers, schedule jobs, or
print connection strings.

The operator feeds the file to ``meta_page_garments.py`` / ``meta_ig_garments.py``.
Pacing between Graph calls stays with the operator or robotRZ.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable, Optional, Sequence

from services.pricing import compute_pricing

MAX_IMAGES = 10
MAX_CAPTION_DESC = 180

_PROVIDER_SUFFIX_RE = re.compile(
    r"(?:\s*[-–—|]\s*(?:so\s*chic|las\s+locas|nissie(?:\s+denim)?|holic))+\s*$",
    re.IGNORECASE,
)
_BOILERPLATE_RE = re.compile(r"^Producto importado desde [^|.]+(?:\.\s*|\s*$)")
_SKIP_SIZE_LABELS = {"unico", "único", "unica", "única"}
_SLUG_CLEAN_RE = re.compile(r"[^a-z0-9]+")


def format_ar_price(amount: int) -> str:
    """Pesos with a thousands dot: 28500 → ``$28.500``."""
    value = int(amount)
    sign = "-" if value < 0 else ""
    digits = str(abs(value))
    groups: list[str] = []
    while digits:
        groups.append(digits[-3:])
        digits = digits[:-3]
    return f"{sign}${'.'.join(reversed(groups))}"


def strip_provider_suffix(title: str) -> str:
    """Drop a trailing provider tag such as `` - Sochic`` or `` - So Chic``."""
    clean = " ".join(str(title or "").split())
    stripped = _PROVIDER_SUFFIX_RE.sub("", clean).strip()
    stripped = " ".join(stripped.split())
    return stripped or clean


def slug_token(value: str) -> str:
    return _SLUG_CLEAN_RE.sub("-", str(value or "").strip().lower()).strip("-")


def manifest_id(product) -> str:
    """Stable slug: ``{provider}-{product_id}``, else ``{category}-{product_id}``."""
    product_id = int(product.product_id)
    provider = slug_token(getattr(product, "provider", None) or "")
    if provider:
        return f"{provider}-{product_id}"
    category = getattr(product, "category", None)
    category_slug = slug_token(getattr(category, "slug", None) or "")
    if category_slug:
        return f"{category_slug}-{product_id}"
    return f"producto-{product_id}"


def display_title(product) -> str:
    raw = getattr(product, "item_title", None) or getattr(product, "name", None) or ""
    title = strip_provider_suffix(raw)
    if title:
        return title
    return f"Producto {int(product.product_id)}"


def catalog_price(product) -> int:
    """Integer pesos the shop charges (sale percent applied when it is set)."""
    pricing = compute_pricing(
        getattr(product, "price", None),
        bool(getattr(product, "is_sale", False)),
        getattr(product, "discount_percent", None),
    )
    return int(pricing["precio_final"])


def useful_description(text: Optional[str]) -> str:
    clean = " ".join(str(text or "").split())
    if not clean:
        return ""
    clean = _BOILERPLATE_RE.sub("", clean).strip()
    if not clean or clean.lower().startswith("producto importado desde"):
        return ""
    if len(clean) <= MAX_CAPTION_DESC:
        return clean
    cut = clean[: MAX_CAPTION_DESC - 1]
    trimmed = cut.rsplit(" ", 1)[0].rstrip(" ,.;")
    if len(trimmed) < 40:
        trimmed = cut.rstrip()
    return trimmed + "…"


def size_labels(product) -> list[str]:
    variants = list(getattr(product, "variants", None) or [])

    def sort_key(variant):
        size = getattr(variant, "size", None)
        order = getattr(size, "sort_order", None) if size is not None else None
        code = getattr(size, "code", "") if size is not None else ""
        return (order if isinstance(order, int) else 10**9, str(code or ""), id(variant))

    labels: list[str] = []
    for variant in sorted(variants, key=sort_key):
        if getattr(variant, "activo", True) is False:
            continue
        size = getattr(variant, "size", None)
        if size is None:
            continue
        label = str(getattr(size, "label", None) or getattr(size, "code", None) or "").strip()
        if not label or label.casefold() in _SKIP_SIZE_LABELS:
            continue
        if label not in labels:
            labels.append(label)
    return labels


def build_caption(*, title: str, price: int, description: Optional[str], sizes: Sequence[str]) -> str:
    lines = [title, format_ar_price(price)]
    if sizes:
        lines.append("Talles: " + ", ".join(sizes))
    desc = useful_description(description)
    if desc:
        lines.append(desc)
    return "\n".join(lines)


def image_urls(product, *, limit: int = MAX_IMAGES) -> list[str]:
    """HTTPS URLs only, main image first, capped."""
    raw = list(getattr(product, "images", None) or [])
    decorated = []
    for index, image in enumerate(raw):
        is_main = bool(getattr(image, "is_main", False))
        image_id = getattr(image, "image_id", None)
        ident = image_id if isinstance(image_id, int) else index
        decorated.append((0 if is_main else 1, ident, index, image))
    decorated.sort(key=lambda row: (row[0], row[1], row[2]))
    urls: list[str] = []
    seen: set[str] = set()
    for _, _, _, image in decorated:
        url = str(getattr(image, "url", "") or "").strip()
        if not url.lower().startswith("https://"):
            continue
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)
        if len(urls) >= limit:
            break
    return urls


def build_manifest_item(product) -> dict:
    title = display_title(product)
    price = catalog_price(product)
    sizes = size_labels(product)
    caption = build_caption(
        title=title,
        price=price,
        description=getattr(product, "description", None),
        sizes=sizes,
    )
    return {
        "id": manifest_id(product),
        "title": title,
        "caption": caption,
        "message": caption,
        "price": price,
        "images": image_urls(product),
    }


def _exclude_keys(product) -> set[str]:
    keys = {manifest_id(product).casefold(), str(int(product.product_id))}
    cod = str(getattr(product, "cod_product", "") or "").strip()
    if cod:
        keys.add(cod.casefold())
    return keys


def select_products(
    products: Iterable,
    *,
    product_ids: Optional[set[int]] = None,
    provider: Optional[str] = None,
    exclude: Optional[Iterable[str]] = None,
    limit: int = 0,
) -> list:
    """Keep caller order. ``limit`` 0 means no cap. Inactive rows stay."""
    provider_norm = (provider or "").strip().lower() or None
    excluded = {str(token).strip().casefold() for token in (exclude or []) if str(token).strip()}
    chosen = []
    for product in products:
        if product_ids is not None and int(product.product_id) not in product_ids:
            continue
        row_provider = str(getattr(product, "provider", "") or "").strip().lower()
        if provider_norm and row_provider != provider_norm:
            continue
        if excluded and (_exclude_keys(product) & excluded):
            continue
        chosen.append(product)
        if limit and len(chosen) >= limit:
            break
    return chosen


def parse_exclude_tokens(text: str) -> list[str]:
    """Ids from a comma-separated line, a newline list, or a JSON array."""
    raw = str(text or "").lstrip("\ufeff").strip()
    if not raw:
        return []
    if raw.startswith("["):
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("El archivo de exclusión debe ser un array JSON o una lista de ids.")
        tokens: list[str] = []
        for item in data:
            if isinstance(item, dict):
                item = item.get("id", "")
            token = str(item).strip()
            if token and not token.startswith("#"):
                tokens.append(token)
        return tokens
    tokens = []
    for line in raw.splitlines() or [raw]:
        body = line.split("#", 1)[0].strip()
        if not body:
            continue
        for part in body.split(","):
            token = part.strip()
            if token:
                tokens.append(token)
    return tokens


def read_exclude_file(path: str) -> list[str]:
    file = Path(path)
    try:
        text = file.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise SystemExit(f"No se pudo leer --exclude-file ({file}): {exc.strerror or exc}") from exc
    try:
        return parse_exclude_tokens(text)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"No se pudo leer --exclude-file ({file}): JSON inválido.") from exc
    except ValueError as exc:
        raise SystemExit(f"No se pudo leer --exclude-file ({file}): {exc}") from exc


def render_manifest(items: Sequence[dict]) -> bytes:
    """UTF-8 JSON array without a BOM."""
    text = json.dumps(list(items), ensure_ascii=False, indent=2)
    if not text.endswith("\n"):
        text += "\n"
    data = text.encode("utf-8")
    if data.startswith(b"\xef\xbb\xbf"):
        raise RuntimeError("El manifiesto no debe llevar BOM.")
    return data


def write_manifest(path: Path, items: Sequence[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(render_manifest(items))


def format_summary(items: Sequence[dict], output: Optional[str], *, dry_run: bool) -> str:
    destination = output or "(sin --output)"
    action = "dry-run (no se escribió el archivo)" if dry_run else "escrito"
    noun = "producto" if len(items) == 1 else "productos"
    lines = [f"{action}: {len(items)} {noun} → {destination}"]
    for item in items:
        lines.append(f"{item['id']}\t{item['title']}\timágenes={len(item['images'])}")
    return "\n".join(lines) + "\n"


def load_products(
    session,
    *,
    product_ids: Optional[set[int]] = None,
    provider: Optional[str] = None,
    exclude: Optional[Iterable[str]] = None,
    limit: int = 0,
) -> list:
    """Newest ``product_id`` first. Includes inactive products."""
    from sqlalchemy import func
    from sqlalchemy.orm import joinedload

    from database.models.ProductVariant import ProductVariant
    from database.models.Products import Products

    query = session.query(Products).options(
        joinedload(Products.images),
        joinedload(Products.category),
        joinedload(Products.variants).joinedload(ProductVariant.size),
    )
    if product_ids:
        query = query.filter(Products.product_id.in_(sorted(product_ids)))
    provider_norm = (provider or "").strip().lower()
    if provider_norm:
        query = query.filter(func.lower(Products.provider) == provider_norm)
    query = query.order_by(Products.product_id.desc())
    rows = []
    seen: set[int] = set()
    for row in query.all():
        if row.product_id in seen:
            continue
        seen.add(row.product_id)
        rows.append(row)
    return select_products(
        rows,
        product_ids=product_ids,
        provider=provider_norm or None,
        exclude=exclude,
        limit=limit,
    )


def fetch_products(
    *,
    product_ids: Optional[set[int]] = None,
    provider: Optional[str] = None,
    exclude: Optional[Iterable[str]] = None,
    limit: int = 0,
) -> list:
    from database.init_db import SessionLocal

    session = SessionLocal()
    try:
        return load_products(
            session,
            product_ids=product_ids,
            provider=provider,
            exclude=exclude,
            limit=limit,
        )
    finally:
        session.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m services.meta_manifest",
        description=(
            "Exporta Products + ProductImages a un manifiesto JSON para robotRZ "
            "(meta_page_garments.py / meta_ig_garments.py). "
            "Solo notebook. No publica en Meta ni llama a Graph."
        ),
        epilog=(
            "Ejemplos:\n"
            "  python -m services.meta_manifest --provider sochic --limit 5 "
            "--output exports/sochic-meta.json --dry-run\n"
            "  python -m services.meta_manifest --product-id 300 --product-id 292 "
            "--exclude-id sochic-300 --output exports/lote.json --dry-run\n"
            "  python -m services.meta_manifest --provider sochic --limit 20 "
            "--exclude-file exports/ya-publicados.txt --output exports/sochic-meta.json\n"
            "Siempre --dry-run antes de escribir. "
            "Guía: docs/ops/meta-garments-manifest.md"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--product-id",
        action="append",
        type=int,
        dest="product_ids",
        default=[],
        help="Id numérico de products.product_id. Se puede repetir.",
    )
    parser.add_argument(
        "--provider",
        default="",
        help="Filtra products.provider (sochic, nissie, laslocas, holic, …).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Máximo después de filtros y exclusiones. 0 = sin tope. Los más nuevos primero.",
    )
    parser.add_argument(
        "--exclude-id",
        action="append",
        dest="exclude_ids",
        default=[],
        help="Slug (sochic-300), product_id o cod_product a omitir. Repetible o separado por comas.",
    )
    parser.add_argument(
        "--exclude-file",
        default="",
        help="Lista de ids ya publicados: un id por línea, comas, o un array JSON. # comenta.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Ruta del JSON. Obligatoria salvo en --dry-run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Imprime ids, títulos, cantidad de imágenes y la ruta. No escribe el archivo.",
    )
    return parser


def _collect_exclude(args) -> set[str]:
    tokens: list[str] = []
    for raw in args.exclude_ids or []:
        tokens.extend(parse_exclude_tokens(raw))
    if args.exclude_file:
        tokens.extend(read_exclude_file(args.exclude_file))
    return {token.casefold() for token in tokens}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.limit < 0:
        parser.error("--limit no puede ser negativo")
    for product_id in args.product_ids or []:
        if product_id <= 0:
            parser.error("--product-id tiene que ser un entero positivo")
    if not args.dry_run and not args.output:
        parser.error("--output es obligatorio (o usá --dry-run)")
    try:
        exclude = _collect_exclude(args)
    except SystemExit:
        raise
    except Exception:
        print("No se pudo armar la lista de exclusión.", file=sys.stderr)
        return 1
    try:
        products = fetch_products(
            product_ids=set(args.product_ids or []) or None,
            provider=args.provider,
            exclude=exclude,
            limit=args.limit,
        )
    except Exception:
        print(
            "No se pudo leer productos. Revisá la conexión en el .env local.",
            file=sys.stderr,
        )
        return 1
    items = [build_manifest_item(product) for product in products]
    output = args.output or None
    if not args.dry_run:
        try:
            write_manifest(Path(args.output), items)
        except Exception:
            print(f"No se pudo escribir {args.output}.", file=sys.stderr)
            return 1
    sys.stdout.write(format_summary(items, output, dry_run=args.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
