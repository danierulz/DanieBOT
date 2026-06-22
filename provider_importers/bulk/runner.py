"""CLI runner for bulk provider catalog imports."""

from __future__ import annotations

import argparse
import json
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from database.init_db import SessionLocal, get_db_session
from gcs.storage_factory import create_uploader
from provider_importers.bulk.delays import REQUEST_DELAY_MS
from provider_importers.bulk.laslocas_catalog import discover_laslocas_product_urls
from provider_importers.bulk.nissie_catalog import discover_nissie_product_urls
from provider_importers.bulk.holic_catalog import discover_holic_product_urls
from provider_importers.bulk.types import BulkImportOptions, BulkImportSummary
from provider_importers.holic import fetch_holic_product
from provider_importers.laslocas import _authenticated_session, fetch_laslocas_product
from provider_importers.nissie import fetch_nissie_product
from provider_importers.registry import detect_provider, fetch_product
from provider_importers.types import ProviderImportError
from services.laslocas_bulk_import import (
    create_bulk_run as create_laslocas_bulk_run,
    run_laslocas_bulk_import,
)
from services.nissie_bulk_import import create_bulk_run as create_nissie_bulk_run, run_nissie_bulk_import
from services.holic_bulk_import import create_bulk_run as create_holic_bulk_run, run_holic_bulk_import
from services.product_variants import sync_product_variants
from services.provider_import import ProviderImportPayload, match_import_color_ids, persist_imported_product


def discover_urls(options: BulkImportOptions) -> list[str]:
    if options.urls:
        return list(options.urls)
    if options.provider == "laslocas":
        session = _authenticated_session()
        return discover_laslocas_product_urls(
            session,
            category_id=options.category_id,
            all_categories=options.all_categories,
            max_pages=options.max_pages,
        )
    if options.provider == "nissie":
        return discover_nissie_product_urls()
    if options.provider == "holic":
        return discover_holic_product_urls()
    raise SystemExit(f"Proveedor no soportado para bulk: {options.provider}")


def run_bulk_import_cli(options: BulkImportOptions) -> BulkImportSummary:
    from database.models.Products import Products

    summary = BulkImportSummary(provider=options.provider)
    urls = discover_urls(options)
    summary.discovered = len(urls)

    if options.dry_run:
        print(json.dumps({"dry_run": True, **summary.to_dict(), "urls": urls}, ensure_ascii=False, indent=2))
        return summary

    uploader = create_uploader()
    payload = ProviderImportPayload(
        status=options.status,
        category_id=options.import_category_id,
        size_code=options.size_code,
    )

    with get_db_session() as db:
        existing_codes = {
            row[0]
            for row in db.query(Products.cod_product).filter(Products.cod_product.isnot(None)).all()
            if row[0]
        }

        for url in urls:
            try:
                if options.provider == "laslocas":
                    imported = fetch_laslocas_product(url)
                elif options.provider == "nissie":
                    imported = fetch_nissie_product(url)
                elif options.provider == "holic":
                    imported = fetch_holic_product(url)
                else:
                    detect_provider(url)
                    imported = fetch_product(url)

                if imported.cod_product in existing_codes:
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

    print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
    return summary


def run_tracked_bulk_import(
    provider: str,
    *,
    category_id: str | None = None,
    all_categories: bool = False,
    max_pages: int = 0,
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
            )
            return run.run_id
        raise SystemExit(f"Proveedor no soportado: {provider}")
    finally:
        db.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bulk import de catálogos de proveedores")
    parser.add_argument("--provider", required=True, choices=["laslocas", "nissie", "holic"])
    parser.add_argument("--url", action="append", dest="urls", default=[])
    parser.add_argument("--category", dest="category_id", help="ID de categoría Las Locas (ej. denim)")
    parser.add_argument("--all-categories", action="store_true")
    parser.add_argument("--max-pages", type=int, default=0, help="0 = todas las páginas del listado")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delay-ms", type=int, default=REQUEST_DELAY_MS)
    parser.add_argument("--status-active", action="store_true", help="Publicar productos activos al importar")
    parser.add_argument("--import-category-id", type=int, default=None)
    parser.add_argument("--size-code", default="UNICO")
    parser.add_argument("--tracked-run", action="store_true", help="Persistir run en provider_import_runs")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.tracked_run:
        if args.dry_run:
            options = BulkImportOptions(
                provider=args.provider,
                dry_run=True,
                category_id=args.category_id,
                all_categories=args.all_categories,
                max_pages=args.max_pages,
                urls=args.urls,
            )
            run_bulk_import_cli(options)
            return 0
        run_id = run_tracked_bulk_import(
            args.provider,
            category_id=args.category_id,
            all_categories=args.all_categories,
            max_pages=args.max_pages,
        )
        print(json.dumps({"ok": True, "run_id": run_id}, ensure_ascii=False))
        return 0

    options = BulkImportOptions(
        provider=args.provider,
        dry_run=args.dry_run,
        delay_ms=args.delay_ms,
        category_id=args.category_id,
        all_categories=args.all_categories,
        max_pages=args.max_pages,
        status=args.status_active,
        import_category_id=args.import_category_id,
        size_code=args.size_code,
        urls=args.urls,
    )
    summary = run_bulk_import_cli(options)
    return 1 if summary.failed else 0


if __name__ == "__main__":
    sys.exit(main())
