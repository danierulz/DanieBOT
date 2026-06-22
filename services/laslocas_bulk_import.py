"""Bulk import orchestration for Las Locas catalog."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy.orm import Session

from database.models.ProviderImportRun import ProviderImportRun
from database.models.ProviderImportRunItem import ProviderImportRunItem
from database.models.Products import Products
from provider_importers.bulk.laslocas_catalog import discover_laslocas_product_urls
from provider_importers.laslocas import _authenticated_session, fetch_laslocas_product
from provider_importers.types import ProviderImportError
from services.provider_import import ProviderImportPayload, persist_imported_product, truncate

from provider_importers.bulk.delays import REQUEST_DELAY_SECONDS

PROVIDER = "laslocas"


class BulkImportConflictError(Exception):
    """Raised when a bulk import is already running for the provider."""


def get_active_run(db: Session, provider: str = PROVIDER) -> ProviderImportRun | None:
    return (
        db.query(ProviderImportRun)
        .filter(ProviderImportRun.provider == provider, ProviderImportRun.status == "running")
        .order_by(ProviderImportRun.run_id.desc())
        .first()
    )


def create_bulk_run(db: Session, *, triggered_by: str | None) -> ProviderImportRun:
    active = get_active_run(db)
    if active:
        raise BulkImportConflictError("Ya hay una importación masiva de Las Locas en curso.")

    run = ProviderImportRun(
        provider=PROVIDER,
        status="running",
        triggered_by=triggered_by,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def run_laslocas_bulk_import(
    db: Session,
    run_id: int,
    uploader,
    *,
    sync_variants_fn: Callable,
    match_color_ids_fn: Callable,
    category_id: str | None = None,
    all_categories: bool = False,
    max_pages: int = 0,
) -> None:
    run = db.query(ProviderImportRun).filter(ProviderImportRun.run_id == run_id).one()
    session = _authenticated_session()

    try:
        urls = discover_laslocas_product_urls(
            session,
            category_id=category_id,
            all_categories=all_categories,
            max_pages=max_pages,
        )
        run.discovered = len(urls)
        db.commit()

        existing_codes = {
            row[0]
            for row in db.query(Products.cod_product).filter(Products.cod_product.isnot(None)).all()
            if row[0]
        }
        payload = ProviderImportPayload(status=False)

        for url in urls:
            try:
                imported = fetch_laslocas_product(url)
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
                logging.exception("laslocas bulk import failed for %s", url)
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

        run.status = "completed"
        run.finished_at = datetime.now(timezone.utc)
    except Exception:
        logging.exception("laslocas bulk import run %s aborted", run_id)
        run.status = "failed"
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise
    else:
        db.commit()


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
