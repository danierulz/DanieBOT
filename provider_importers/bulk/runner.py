"""CLI runner for bulk provider catalog imports.

Notebook only. Do not schedule this module on Cloud Run, Cloud Scheduler,
or GitHub Actions.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from database.init_db import SessionLocal, get_db_session
from gcs.storage_factory import create_uploader
from provider_importers.bulk.brands import (
    NOTEBOOK_BANNER,
    format_brand_list,
    get_brand,
    load_brand_registry,
    missing_login_env,
)
from provider_importers.bulk.existing import (
    read_known_source_urls,
    remember_source_url,
    select_import_urls,
)
from provider_importers.bulk.holic_catalog import discover_holic_product_urls
from provider_importers.bulk.laslocas_catalog import discover_laslocas_product_urls
from provider_importers.bulk.nissie_catalog import discover_nissie_product_urls
from provider_importers.bulk.sochic_catalog import discover_sochic_product_urls
from provider_importers.bulk.types import BulkImportOptions, BulkImportSummary
from provider_importers.holic import fetch_holic_product
from provider_importers.laslocas import _authenticated_session, fetch_laslocas_product
from provider_importers.nissie import fetch_nissie_product
from provider_importers.sochic import fetch_sochic_product
from provider_importers.types import ProviderImportError
from services.holic_bulk_import import create_bulk_run as create_holic_bulk_run
from services.holic_bulk_import import run_holic_bulk_import
from services.laslocas_bulk_import import create_bulk_run as create_laslocas_bulk_run
from services.laslocas_bulk_import import run_laslocas_bulk_import
from services.nissie_bulk_import import create_bulk_run as create_nissie_bulk_run
from services.nissie_bulk_import import run_nissie_bulk_import
from services.product_variants import sync_product_variants
from services.provider_import import ProviderImportPayload, match_import_color_ids, persist_imported_product

_FETCHERS = {
    "laslocas": fetch_laslocas_product,
    "nissie": fetch_nissie_product,
    "holic": fetch_holic_product,
    "sochic": fetch_sochic_product,
}


def discover_urls(options: BulkImportOptions) -> list[str]:
    if options.urls:
        return list(options.urls)
    brand = get_brand(options.provider)
    if brand.mode == "urls_only":
        raise SystemExit(
            f"{brand.display_name} ({brand.id}) no tiene descubrimiento de listado. "
            "Pasá una o más fichas con --url."
        )
    if brand.id == "laslocas":
        session = _authenticated_session()
        return discover_laslocas_product_urls(
            session,
            category_id=options.category_id,
            all_categories=options.all_categories,
            max_pages=options.max_pages,
        )
    if brand.id == "nissie":
        return discover_nissie_product_urls()
    if brand.id == "holic":
        return discover_holic_product_urls()
    if brand.id == "sochic":
        return discover_sochic_product_urls(
            category_slug=options.category_id,
            max_pages=options.max_pages,
        )
    raise SystemExit(
        f"No hay descubrimiento masivo para {brand.id} (mode={brand.mode}). "
        "Pasá fichas con --url."
    )


def run_bulk_import_cli(options: BulkImportOptions) -> BulkImportSummary:
    from database.models.Products import Products

    summary = BulkImportSummary(provider=options.provider)
    urls = discover_urls(options)
    summary.discovered = len(urls)
    known = read_known_source_urls() if options.skip_existing else set()
    selection = select_import_urls(
        urls,
        skip_existing=options.skip_existing,
        known_urls=known,
        limit=options.limit,
    )
    summary.skipped_existing = len(selection.skipped_existing)

    if options.dry_run:
        payload = {
            "dry_run": True,
            **summary.to_dict(),
            "skip_existing": options.skip_existing,
            "would_skip_existing": summary.skipped_existing,
            "would_fetch": len(selection.to_fetch),
            "limit": options.limit,
            "delay_ms": options.delay_ms,
            "urls": list(selection.to_fetch),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return summary

    summary.skipped += summary.skipped_existing
    uploader = create_uploader()
    payload = ProviderImportPayload(
        status=options.status,
        category_id=options.import_category_id,
        size_code=options.size_code,
    )
    fetcher = _FETCHERS.get(options.provider)
    if fetcher is None:
        raise SystemExit(f"Proveedor no soportado para bulk: {options.provider}")

    with get_db_session() as db:
        existing_codes = {
            row[0]
            for row in db.query(Products.cod_product).filter(Products.cod_product.isnot(None)).all()
            if row[0]
        }

        for url in selection.to_fetch:
            try:
                imported = fetcher(url)
                if imported.cod_product in existing_codes:
                    remember_source_url(db, imported.cod_product, url)
                    summary.skipped += 1
                    continue

                result = persist_imported_product(
                    db,
                    imported,
                    payload,
                    uploader,
                    sync_variants_fn=sync_product_variants,
                    match_color_ids_fn=match_import_color_ids,
                )
                if result.get("created"):
                    existing_codes.add(imported.cod_product)
                    summary.created += 1
                else:
                    summary.skipped += 1
            except ProviderImportError as exc:
                summary.failed += 1
                summary.errors.append({"url": url, "error": str(exc)})
            except Exception as exc:
                summary.failed += 1
                summary.errors.append({"url": url, "error": str(exc)})

            if options.delay_ms > 0:
                time.sleep(options.delay_ms / 1000.0)

    printed = summary.to_dict()
    printed["skip_existing"] = options.skip_existing
    printed["limit"] = options.limit
    printed["delay_ms"] = options.delay_ms
    print(json.dumps(printed, ensure_ascii=False, indent=2))
    return summary


def run_tracked_bulk_import(
    provider: str,
    *,
    category_id: str | None = None,
    all_categories: bool = False,
    max_pages: int = 0,
    limit: int = 0,
    skip_existing: bool = True,
    triggered_by: str = "cli",
) -> int:
    uploader = create_uploader()
    db = SessionLocal()
    try:
        if provider == "laslocas":
            run = create_laslocas_bulk_run(db, triggered_by=triggered_by)
            run_laslocas_bulk_import(
                db,
                run.run_id,
                uploader,
                sync_variants_fn=sync_product_variants,
                match_color_ids_fn=match_import_color_ids,
                category_id=category_id,
                all_categories=all_categories,
                max_pages=max_pages,
                limit=limit,
                skip_existing=skip_existing,
            )
            return run.run_id
        if provider == "nissie":
            run = create_nissie_bulk_run(db, triggered_by=triggered_by)
            run_nissie_bulk_import(
                db,
                run.run_id,
                uploader,
                sync_variants_fn=sync_product_variants,
                match_color_ids_fn=match_import_color_ids,
                limit=limit,
                skip_existing=skip_existing,
            )
            return run.run_id
        if provider == "holic":
            run = create_holic_bulk_run(db, triggered_by=triggered_by)
            run_holic_bulk_import(
                db,
                run.run_id,
                uploader,
                sync_variants_fn=sync_product_variants,
                match_color_ids_fn=match_import_color_ids,
                limit=limit,
                skip_existing=skip_existing,
            )
            return run.run_id
        raise SystemExit(
            f"{provider} no tiene corrida tracked. "
            "Usá el CLI de notebook sin --tracked-run."
        )
    finally:
        db.close()


def build_parser() -> argparse.ArgumentParser:
    brand_ids = load_brand_registry().ids()
    parser = argparse.ArgumentParser(
        description=(
            "Alta masiva de catálogos de proveedores. "
            "Solo notebook local: no programar en Cloud Run ni Cloud Scheduler."
        ),
        epilog=(
            "Ejemplos:\n"
            "  python -m provider_importers.bulk.runner --list-brands\n"
            "  python -m provider_importers.bulk.runner --provider laslocas "
            "--category denim --max-pages 1 --limit 5 --dry-run\n"
            "  python -m provider_importers.bulk.runner --provider sochic "
            "--max-pages 1 --limit 5 --dry-run\n"
            "Siempre --dry-run antes de escribir. Guía: docs/specs/17-scraping-masivo-proveedores.md"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--provider", choices=brand_ids, help="Id en brands.json")
    parser.add_argument(
        "--list-brands",
        action="store_true",
        help="Mostrar marcas de brands.json y salir",
    )
    parser.add_argument("--url", action="append", dest="urls", default=[])
    parser.add_argument(
        "--category",
        dest="category_id",
        help="Las Locas: id de laslocas_categories.json. So Chic: slug de product-category.",
    )
    parser.add_argument("--all-categories", action="store_true")
    parser.add_argument("--max-pages", type=int, default=0, help="0 = todas las páginas del listado")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Tras saltear existentes, fetchear como máximo N fichas nuevas. 0 = sin tope.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--delay-ms",
        type=int,
        default=None,
        help="Pausa entre fichas. Si se omite, usa default_delay_ms de la marca.",
    )
    parser.add_argument(
        "--skip-existing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "No scrapear URLs ya guardadas (default). "
            "--no-skip-existing vuelve a bajarlas; el alta igual no pisa cod_product."
        ),
    )
    parser.add_argument("--status-active", action="store_true", help="Publicar productos activos al importar")
    parser.add_argument("--import-category-id", type=int, default=None)
    parser.add_argument("--size-code", default="UNICO")
    parser.add_argument("--tracked-run", action="store_true", help="Persistir run en provider_import_runs")
    return parser


def _warn_ignored_flags(brand, args) -> None:
    if args.urls and (args.category_id or args.all_categories or args.max_pages):
        print(
            "aviso: --url reemplaza el descubrimiento; se ignoran --category, --all-categories y --max-pages.",
            file=sys.stderr,
        )
        return
    if brand.mode == "catalog" and brand.id != "sochic":
        if args.category_id:
            print(f"aviso: --category no aplica a {brand.id}.", file=sys.stderr)
        if args.all_categories:
            print(f"aviso: --all-categories no aplica a {brand.id}.", file=sys.stderr)
        if args.max_pages:
            print(
                f"aviso: --max-pages no aplica a {brand.id}. Usá --limit para acotar fichas nuevas.",
                file=sys.stderr,
            )
    if brand.id == "sochic" and args.all_categories:
        print(
            "aviso: So Chic no recorre todas las categorías. "
            "Pasá --category <slug> o dejá el shop completo.",
            file=sys.stderr,
        )


def _needs_login(brand, args) -> bool:
    if not brand.requires_login:
        return False
    if args.dry_run and args.urls:
        return False
    return True


def _options_from_args(args, brand) -> BulkImportOptions:
    if args.delay_ms is not None and args.delay_ms < 0:
        raise SystemExit("--delay-ms no puede ser negativo")
    delay_ms = brand.default_delay_ms if args.delay_ms is None else args.delay_ms
    return BulkImportOptions(
        provider=args.provider,
        dry_run=args.dry_run,
        delay_ms=delay_ms,
        category_id=args.category_id,
        all_categories=args.all_categories,
        max_pages=args.max_pages,
        status=args.status_active,
        import_category_id=args.import_category_id,
        size_code=args.size_code,
        urls=list(args.urls or []),
        limit=args.limit,
        skip_existing=args.skip_existing,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.list_brands:
        print(format_brand_list(), end="")
        return 0
    if not args.provider:
        parser.error("el argumento --provider es obligatorio (o usá --list-brands)")
    if args.limit < 0:
        parser.error("--limit no puede ser negativo")
    if args.max_pages < 0:
        parser.error("--max-pages no puede ser negativo")

    brand = get_brand(args.provider)
    print(NOTEBOOK_BANNER, file=sys.stderr)
    _warn_ignored_flags(brand, args)
    if args.tracked_run and brand.id == "sochic":
        raise SystemExit(
            "So Chic no registra provider_import_runs (--tracked-run). "
            "Corré el alta en el notebook sin --tracked-run."
        )
    if _needs_login(brand, args):
        missing = missing_login_env(brand)
        if missing:
            names = ", ".join(missing)
            raise SystemExit(
                f"{brand.display_name} requiere {names} en el .env local del notebook. "
                "No se muestran los valores."
            )
    if args.tracked_run and not args.dry_run and args.urls:
        print(
            "aviso: --tracked-run descubre el catálogo y no usa --url.",
            file=sys.stderr,
        )

    if args.tracked_run:
        if args.dry_run:
            run_bulk_import_cli(_options_from_args(args, brand))
            return 0
        run_id = run_tracked_bulk_import(
            args.provider,
            category_id=args.category_id,
            all_categories=args.all_categories,
            max_pages=args.max_pages,
            limit=args.limit,
            skip_existing=args.skip_existing,
        )
        print(json.dumps({"ok": True, "run_id": run_id}, ensure_ascii=False))
        return 0

    try:
        summary = run_bulk_import_cli(_options_from_args(args, brand))
    except ProviderImportError as exc:
        raise SystemExit(str(exc)) from exc
    return 1 if summary.failed else 0


if __name__ == "__main__":
    sys.exit(main())
