"""Bulk import orchestration for Nissie Denim catalog."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Callable

import requests
from sqlalchemy.orm import Session

from database.models.ProviderImportRun import ProviderImportRun
from database.models.ProviderImportRunItem import ProviderImportRunItem
from database.models.Products import Products
from provider_importers.nissie import fetch_nissie_product
from provider_importers.nissie_catalog import discover_nissie_product_urls
from provider_importers.types import ProviderImportError
from services.provider_import import ProviderImportPayload, persist_imported_product, truncate

from provider_importers.bulk.delays import REQUEST_DELAY_SECONDS

PROVIDER = "nissie"


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
        raise BulkImportConflictError("Ya hay una importación masiva de Nissie en curso.")

    run = ProviderImportRun(
        provider=PROVIDER,
        status="running",
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
        urls = discover_nissie_product_urls(session)
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

        run.status = "completed"
        run.finished_at = datetime.now(timezone.utc)
    except Exception:
        logging.exception("nissie bulk import run %s aborted", run_id)
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


def serialize_run(db: Session, run: ProviderImportRun, *, include_failed: bool = True) -> dict:
    failed_items = []
    if include_failed:
        failed_items = (
            db.query(ProviderImportRunItem)
            .filter(
                ProviderImportRunItem.run_id == run.run_id,
                ProviderImportRunItem.status == "failed",
            )
            .order_by(ProviderImportRunItem.item_id.asc())
            .limit(100)
            .all()
        )
    processed = run.created + run.skipped + run.failed
    return {
        "run_id": run.run_id,
        "provider": run.provider,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "discovered": run.discovered,
        "created": run.created,
        "skipped": run.skipped,
        "failed": run.failed,
        "processed": processed,
        "triggered_by": run.triggered_by,
        "failed_items": [
            {
                "source_url": item.source_url,
                "cod_product": item.cod_product,
                "error_message": item.error_message,
            }
            for item in failed_items
        ],
    }
