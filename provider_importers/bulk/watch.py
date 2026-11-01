"""Local listing watch: what is new vs already imported.

Notebook / PC only. This module reads the first listing page and classifies
URLs. It does not insert products, publish to Meta, or schedule a job.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Callable

from provider_importers.bulk.brands import get_brand, missing_login_env
from provider_importers.bulk.existing import DedupIndex, canonical_source_url
from provider_importers.bulk.watch_listings import (
    ListingHit,
    ListingPage,
    WatchListingError,
    fetch_provider_listing,
)

DEFAULT_WATCH_PROVIDERS = ("laslocas", "nissie", "sochic")
ALLOWED_WATCH_PROVIDERS = frozenset((*DEFAULT_WATCH_PROVIDERS, "holic"))
WATCH_LIMITS = frozenset({5, 10})
DEFAULT_WATCH_LIMIT = 5
SOCHIC_MIN_PAUSE_SECONDS = 5.0

STATUS_NEW = "nuevo"
STATUS_DUPLICATE = "posible_duplicado"
MATCH_PRODUCT_URL = "provider_source_url"
MATCH_RUN = "import_run"
MATCH_CODE = "cod_product"

WATCH_NOTICE = (
    "Solo laptop. No publica a Meta. No importa todo solo. "
    "Mira la primera página del listado (5 o 10 fichas por proveedor) "
    "y marca nuevo o posible duplicado. "
    "No agenda Cloud Run, Cloud Scheduler ni un cron."
)

_MATCH_LABELS = {
    MATCH_PRODUCT_URL: "URL ya guardada",
    MATCH_RUN: "corrida de importación",
    MATCH_CODE: "mismo código",
}
_SECRET_ENV = ("LOGIN_EMAIL", "LOGIN_PASS", "DATABASE_URL", "DB_PASSWORD")


class WatchRequestError(ValueError):
    """The admin asked for a limit or provider this tab does not run."""


class WatchNotLocalError(RuntimeError):
    """The watch must not run on Cloud Run."""


@dataclass(frozen=True)
class WatchItem:
    provider: str
    provider_name: str
    title: str | None
    url: str
    price: int | None
    status: str
    status_label: str
    match: str | None
    match_label: str | None
    cod_product: str | None

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "provider_name": self.provider_name,
            "title": self.title,
            "url": self.url,
            "price": self.price,
            "status": self.status,
            "status_label": self.status_label,
            "match": self.match,
            "match_label": self.match_label,
            "cod_product": self.cod_product,
        }


@dataclass
class ProviderWatchResult:
    provider: str
    display_name: str
    delay_ms: int
    listing_pages: int
    discovered_on_page: int
    shown: int
    error: str | None = None
    cli_dry_run: str = ""
    items: list[WatchItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.provider,
            "display_name": self.display_name,
            "delay_ms": self.delay_ms,
            "listing_pages": self.listing_pages,
            "discovered_on_page": self.discovered_on_page,
            "shown": self.shown,
            "error": self.error,
            "cli_dry_run": self.cli_dry_run,
        }


@dataclass
class WatchReport:
    limit: int
    providers: list[ProviderWatchResult]
    items: list[WatchItem]

    def to_dict(self) -> dict:
        return {
            "ok": True,
            "notebook_only": True,
            "imports": False,
            "publishes_meta": False,
            "limit": self.limit,
            "notice": WATCH_NOTICE,
            "providers": [row.to_dict() for row in self.providers],
            "items": [row.to_dict() for row in self.items],
        }


def local_watch_block_reason() -> str | None:
    """Cloud Run sets ``K_SERVICE``. There is no scheduler to register."""
    if os.environ.get("K_SERVICE"):
        return (
            "Novedades de proveedores solo se consulta en la PC. "
            "No corre en Cloud Run, Cloud Scheduler ni un cron."
        )
    return None


def normalize_watch_limit(limit: object) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int) or limit not in WATCH_LIMITS:
        raise WatchRequestError("El máximo por proveedor es 5 o 10.")
    return limit


def normalize_watch_providers(providers: object) -> list[str]:
    if providers is None:
        return list(DEFAULT_WATCH_PROVIDERS)
    if not isinstance(providers, list) or not providers:
        raise WatchRequestError("Elegí al menos un proveedor.")
    chosen: list[str] = []
    for item in providers:
        if not isinstance(item, str):
            raise WatchRequestError("Proveedor inválido.")
        provider_id = item.strip().lower()[:32]
        if provider_id not in ALLOWED_WATCH_PROVIDERS:
            raise WatchRequestError(f"Proveedor no incluido en novedades: {provider_id}")
        if provider_id not in chosen:
            chosen.append(provider_id)
    return chosen


def classify_listing_hit(hit: ListingHit, index: DedupIndex) -> tuple[str, str | None]:
    """Return ``(status, match)``.

    Order matches the bulk runner: saved URL, then a successful import-run
    URL, then ``cod_product`` when the listing exposes the same business key.
    """
    key = canonical_source_url(hit.url)
    if key and key in index.product_urls:
        return STATUS_DUPLICATE, MATCH_PRODUCT_URL
    if key and key in index.run_urls:
        return STATUS_DUPLICATE, MATCH_RUN
    code = (hit.cod_product or "").strip()
    if code and code in index.cod_products:
        return STATUS_DUPLICATE, MATCH_CODE
    return STATUS_NEW, None


def redact_secrets(text: str) -> str:
    """Drop env values if a provider error echoed them. Names may remain."""
    cleaned = str(text or "")
    for name in _SECRET_ENV:
        secret = os.getenv(name, "")
        if secret and len(secret) >= 4 and secret in cleaned:
            cleaned = cleaned.replace(secret, "••••")
    return cleaned[:400]


def cli_dry_run_command(provider: str, limit: int, laslocas_category: str) -> str:
    """Notebook command. ``--dry-run`` does not fetch fichas or insert rows."""
    brand = get_brand(provider)
    parts = [
        "python -m provider_importers.bulk.runner",
        "--provider",
        provider,
    ]
    if provider == "laslocas":
        parts.extend(["--category", laslocas_category, "--max-pages", "1"])
    elif provider == "sochic":
        parts.extend(["--max-pages", "1"])
    parts.extend(
        [
            "--limit",
            str(limit),
            "--delay-ms",
            str(max(brand.default_delay_ms, 5000 if provider == "sochic" else 0)),
            "--dry-run",
        ]
    )
    return " ".join(parts)


def pause_before(previous_id: str | None, previous_delay_ms: int, current_id: str, current_delay_ms: int) -> float:
    """Seconds to wait between two listing reads. So Chic never goes under 5s."""
    if not previous_id:
        return 0.0
    wait_ms = max(int(previous_delay_ms), int(current_delay_ms))
    if previous_id == "sochic" or current_id == "sochic":
        wait_ms = max(wait_ms, int(SOCHIC_MIN_PAUSE_SECONDS * 1000))
    return wait_ms / 1000.0


def scan_watch(
    *,
    providers: list[str],
    limit: int,
    index: DedupIndex,
    laslocas_category: str = "denim",
    fetch: Callable[..., ListingPage] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> WatchReport:
    """Classify the first listing page of each provider. Does not import."""
    fetch_fn = fetch if fetch is not None else fetch_provider_listing
    pause = sleep if sleep is not None else time.sleep
    chosen = normalize_watch_providers(providers)
    capped = normalize_watch_limit(limit)
    category = (laslocas_category or "denim").strip() or "denim"
    results: list[ProviderWatchResult] = []
    items: list[WatchItem] = []
    previous_id: str | None = None
    previous_delay = 0

    for provider_id in chosen:
        brand = get_brand(provider_id)
        wait = pause_before(previous_id, previous_delay, brand.id, brand.default_delay_ms)
        if wait:
            pause(wait)
        previous_id = brand.id
        previous_delay = brand.default_delay_ms
        result = ProviderWatchResult(
            provider=brand.id,
            display_name=brand.display_name,
            delay_ms=brand.default_delay_ms,
            listing_pages=1,
            discovered_on_page=0,
            shown=0,
            cli_dry_run=cli_dry_run_command(brand.id, capped, category),
        )
        missing = missing_login_env(brand)
        if missing:
            names = ", ".join(missing)
            result.error = (
                f"Faltan variables en el .env local: {names}. "
                "No se muestran los valores."
            )
            results.append(result)
            continue
        try:
            page = fetch_fn(
                provider=brand.id,
                limit=capped,
                laslocas_category=category,
            )
        except WatchListingError as exc:
            result.error = redact_secrets(str(exc)) or "No se pudo leer el listado."
            results.append(result)
            logging.warning("provider_watch_listing_failed provider=%s", brand.id)
            continue
        except Exception as exc:
            result.error = redact_secrets(str(exc)) or "No se pudo leer el listado."
            results.append(result)
            logging.warning("provider_watch_listing_failed provider=%s", brand.id)
            continue

        hits = list(page.hits)[:capped]
        result.discovered_on_page = int(page.discovered)
        seen: set[str] = set()
        for hit in hits:
            key = canonical_source_url(hit.url)
            if not key or key in seen:
                continue
            seen.add(key)
            status, match = classify_listing_hit(hit, index)
            item = WatchItem(
                provider=brand.id,
                provider_name=brand.display_name,
                title=hit.title,
                url=hit.url,
                price=hit.price,
                status=status,
                status_label="posible duplicado" if status == STATUS_DUPLICATE else "nuevo",
                match=match,
                match_label=_MATCH_LABELS.get(match or ""),
                cod_product=(hit.cod_product or None),
            )
            result.items.append(item)
            items.append(item)
        result.shown = len(result.items)
        results.append(result)

    return WatchReport(limit=capped, providers=results, items=items)
