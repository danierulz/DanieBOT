"""Bulk import orchestration for Nissie Denim catalog."""
from __future__ import annotations

import logging
import time
from typing import Callable

import requests
from sqlalchemy.orm import Session

from database.models.ProviderImportRun import ProviderImportRun
from database.models.ProviderImportRunItem import ProviderImportRunItem
from database.models.Products import Products
from provider_importers.bulk.delays import REQUEST_DELAY_SECONDS
from provider_importers.nissie import fetch_nissie_product
from provider_importers.nissie_catalog import discover_nissie_product_urls
from provider_importers.types import ProviderImportError
from services.provider_import import ProviderImportPayload, persist_imported_product, truncate
from services.provider_import_runs import (
    finish_run,
    get_active_run,
    make_progress_callback,
    set_run_phase,
)

PROVIDER = "nissie"


class BulkImportConflictError(Exception):
    """Raised when a bulk import is already running for the provider."""


def create_bulk_run(db: Session, *, triggered_by: str | None) -> ProviderImportRun:
    active = get_active_run(db, PROVIDER)
    if active:
        raise BulkImportConflictError("Ya hay una importación masiva de Nissie en curso.")

    run = ProviderImportRun(
        provider=PROVIDER,
        status="running",
        phase="discovering",
        progress_detail="Explorando catálogo Nissie…",
        triggered_by=triggered_by,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def run_nissie_bulk_import(
    db: Session,
    run_id: int,
    uploader,
    *,
    sync_variants_fn: Callable,
    match_color_ids_fn: Callable,
) -> None:
    run = db.query(ProviderImportRun).filter(ProviderImportRun.run_id == run_id).one()
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept-Language": "es-AR,es;q=0.9",
        }
    )

    try:
        set_run_phase(db, run, phase="discovering", progress_detail="Explorando catálogo Nissie…")
        on_progress = make_progress_callback(db, run_id)
        urls = discover_nissie_product_urls(session, on_progress=on_progress)
        set_run_phase(
            db,
            run,
            phase="importing",
            progress_detail=f"Importando 0/{len(urls)} productos…",
            discovered=len(urls),
        )

        existing_codes = {
            row[0]
            for row in db.query(Products.cod_product).filter(Products.cod_product.isnot(None)).all()
            if row[0]
        }
        payload = ProviderImportPayload(status=False)

        for url in urls:
            run.progress_detail = truncate(url, 255)
            db.commit()
            try:
                imported = fetch_nissie_product(url)
                if imported.cod_product in existing_codes:
                    _log_item(
                        db,
                        run,
                        source_url=url,
                        cod_product=imported.cod_product,
                        status="skipped",
                    )
                    run.skipped += 1
                    db.commit()
                    time.sleep(REQUEST_DELAY_SECONDS)
                    continue

                result = persist_imported_product(
                    db,
                    imported,
                    payload,
                    uploader,
                    sync_variants_fn=sync_variants_fn,
                    match_color_ids_fn=match_color_ids_fn,
                )
                if result.get("created"):
                    existing_codes.add(imported.cod_product)
                    _log_item(
                        db,
                        run,
                        source_url=url,
                        cod_product=imported.cod_product,
                        status="created",
                        product_id=result.get("id"),
                    )
                    run.created += 1
                else:
                    _log_item(
                        db,
                        run,
                        source_url=url,
                        cod_product=imported.cod_product,
                        status="skipped",
                        product_id=result.get("id"),
                    )
                    run.skipped += 1
                db.commit()
            except ProviderImportError as exc:
                _log_item(
                    db,
                    run,
                    source_url=url,
                    status="failed",
                    error_message=truncate(str(exc), 512),
                )
                run.failed += 1
                db.commit()
            except Exception as exc:
                logging.exception("nissie bulk import failed for %s", url)
                _log_item(
                    db,
                    run,
                    source_url=url,
                    status="failed",
                    error_message=truncate(str(exc), 512),
                )
                run.failed += 1
                db.commit()

            time.sleep(REQUEST_DELAY_SECONDS)

        finish_run(db, run, status="completed", phase="completed")
    except Exception as exc:
        logging.exception("nissie bulk import run %s aborted", run_id)
        run.progress_detail = truncate(str(exc), 255)
        finish_run(db, run, status="failed", phase="failed")
        raise


def _log_item(
    db: Session,
    run: ProviderImportRun,
    *,
    source_url: str,
    status: str,
    cod_product: str | None = None,
    error_message: str | None = None,
    product_id: int | None = None,
) -> None:
    db.add(
        ProviderImportRunItem(
            run_id=run.run_id,
            source_url=source_url,
            cod_product=cod_product,
            status=status,
            error_message=error_message,
            product_id=product_id,
        )
    )
