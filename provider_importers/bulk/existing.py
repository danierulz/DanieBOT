"""Skip catalog URLs that already exist locally, before any product fetch."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from database.init_db import SessionLocal
from database.models.Products import Products
from database.models.ProviderImportRunItem import ProviderImportRunItem


@dataclass(frozen=True)
class ImportUrlSelection:
    discovered: tuple[str, ...]
    skipped_existing: tuple[str, ...]
    to_fetch: tuple[str, ...]


@dataclass(frozen=True)
class DedupIndex:
    """Keys the notebook already knows, using the same rules as ``--skip-existing``.

    ``product_urls`` come from ``products.provider_source_url``.
    ``run_urls`` come from created/skipped import-run items whose ``cod_product``
    still exists. Failed items and rows whose product was deleted stay out.
    ``cod_products`` are the business keys on ``products`` (Nissie group id,
    So Chic SKU+slug, Las Locas code, and the rest).
    """

    product_urls: frozenset[str]
    run_urls: frozenset[str]
    cod_products: frozenset[str]

    @property
    def known_urls(self) -> set[str]:
        return set(self.product_urls) | set(self.run_urls)


def canonical_source_url(url: str | None) -> str:
    """Compare product URLs ignoring scheme, www, query and trailing slash."""
    raw = str(url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return f"https://{host}{path}"


def cap_discovered_urls(urls: list[str], limit: int | None) -> list[str]:
    """Keep the first ``limit`` URLs. ``0`` or ``None`` means no cap."""
    if limit is None or limit == 0:
        return list(urls)
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
        raise ValueError("limit debe ser un entero >= 0")
    return list(urls[:limit])


def select_import_urls(
    urls: list[str],
    *,
    skip_existing: bool,
    known_urls: set[str],
    limit: int = 0,
) -> ImportUrlSelection:
    """Drop URLs already stored locally, then cap how many new ones to fetch.

    ``known_urls`` must already be canonical (see ``canonical_source_url``).
    ``--limit`` applies to the remaining new URLs, so a cap is not spent on
    rows we will not scrape.
    """
    skipped: list[str] = []
    fresh: list[str] = []
    for url in urls:
        key = canonical_source_url(url)
        if skip_existing and key and key in known_urls:
            skipped.append(url)
        else:
            fresh.append(url)
    return ImportUrlSelection(
        discovered=tuple(urls),
        skipped_existing=tuple(skipped),
        to_fetch=tuple(cap_discovered_urls(fresh, limit)),
    )


def load_dedup_index(db: Session) -> DedupIndex:
    """Load URL and ``cod_product`` keys. See ``DedupIndex``."""
    product_urls: set[str] = set()
    for (value,) in db.query(Products.provider_source_url).filter(
        Products.provider_source_url.isnot(None),
        Products.provider_source_url != "",
    ):
        key = canonical_source_url(value)
        if key:
            product_urls.add(key)

    run_urls: set[str] = set()
    rows = (
        db.query(ProviderImportRunItem.source_url)
        .join(Products, Products.cod_product == ProviderImportRunItem.cod_product)
        .filter(ProviderImportRunItem.status.in_(("created", "skipped")))
        .filter(ProviderImportRunItem.cod_product.isnot(None))
        .all()
    )
    for (value,) in rows:
        key = canonical_source_url(value)
        if key:
            run_urls.add(key)

    codes: set[str] = set()
    for (value,) in db.query(Products.cod_product).filter(
        Products.cod_product.isnot(None),
        Products.cod_product != "",
    ):
        code = str(value).strip()
        if code:
            codes.add(code)

    return DedupIndex(
        product_urls=frozenset(product_urls),
        run_urls=frozenset(run_urls),
        cod_products=frozenset(codes),
    )


def load_known_source_urls(db: Session) -> set[str]:
    """Canonical URLs already tied to a product row.

    Sources:
    - ``products.provider_source_url`` (written on each new import)
    - ``provider_import_run_items.source_url`` for created/skipped items whose
      ``cod_product`` still exists (bulk runs from before that column was filled)

    Failed items are ignored so a later run can retry them.
    """
    return load_dedup_index(db).known_urls


def read_known_source_urls() -> set[str]:
    """Load known URLs for the CLI. Connection errors do not echo secrets."""
    db = None
    try:
        db = SessionLocal()
        return load_known_source_urls(db)
    except Exception:
        raise SystemExit(
            "No se pudo leer productos ya importados en la base del notebook. "
            "Revisá DATABASE_URL o DB_* en el .env local. "
            "El detalle no se imprime para no filtrar credenciales."
        )
    finally:
        if db is not None:
            db.close()


def remember_source_url(db: Session, cod_product: str | None, source_url: str | None) -> None:
    """Store the provider URL on an existing row when it is still empty.

    The caller commits. A later run can then skip this URL before fetching.
    """
    code = (cod_product or "").strip()
    raw = (source_url or "").strip()
    if not code or not raw:
        return
    row = db.query(Products).filter(Products.cod_product == code).one_or_none()
    if row is None or row.provider_source_url:
        return
    row.provider_source_url = raw[:512]


def import_progress_detail(to_fetch: int, skipped: int) -> str:
    if skipped:
        return (
            f"Importando 0/{to_fetch} productos "
            f"({skipped} ya en la base, sin scrapear)…"
        )
    return f"Importando 0/{to_fetch} productos…"


def record_preskipped(db: Session, run, urls: list[str], log_item) -> None:
    """Count URLs we will not fetch. ``log_item`` is the per-provider audit helper."""
    for url in urls:
        log_item(db, run, source_url=url, status="skipped")
    run.skipped += len(urls)
    if urls:
        db.commit()


def split_existing_urls(
    db: Session,
    urls: list[str],
    *,
    skip_existing: bool,
    limit: int = 0,
) -> tuple[list[str], list[str]]:
    known = load_known_source_urls(db) if skip_existing else set()
    selection = select_import_urls(
        urls,
        skip_existing=skip_existing,
        known_urls=known,
        limit=limit,
    )
    return list(selection.skipped_existing), list(selection.to_fetch)
