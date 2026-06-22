"""Shared helpers for provider bulk import runs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy.orm import Session

from database.models.ProviderImportRun import ProviderImportRun
from database.models.ProviderImportRunItem import ProviderImportRunItem

STALE_RUN_HOURS = 2
ProgressCallback = Callable[[str, int], None]


def get_active_run(db: Session, provider: str) -> ProviderImportRun | None:
    return (
        db.query(ProviderImportRun)
        .filter(ProviderImportRun.provider == provider, ProviderImportRun.status == "running")
        .order_by(ProviderImportRun.run_id.desc())
        .first()
    )


def make_progress_callback(db: Session, run_id: int) -> ProgressCallback:
    def on_progress(detail: str, urls_found: int) -> None:
        run = db.query(ProviderImportRun).filter(ProviderImportRun.run_id == run_id).one()
        run.progress_detail = detail[:255] if detail else None
        run.discovered = max(int(urls_found), 0)
        db.commit()

    return on_progress


def set_run_phase(
    db: Session,
    run: ProviderImportRun,
    *,
    phase: str,
    progress_detail: str | None = None,
    discovered: int | None = None,
) -> None:
    run.phase = phase
    if progress_detail is not None:
        run.progress_detail = progress_detail[:255] if progress_detail else None
    if discovered is not None:
        run.discovered = discovered
    db.commit()


def finish_run(db: Session, run: ProviderImportRun, *, status: str, phase: str) -> None:
    run.status = status
    run.phase = phase
    run.finished_at = datetime.now(timezone.utc)
    db.commit()


def cancel_run(db: Session, run: ProviderImportRun, *, reason: str = "Cancelada manualmente") -> None:
    run.status = "failed"
    run.phase = "failed"
    run.progress_detail = reason[:255]
    run.finished_at = datetime.now(timezone.utc)
    db.commit()


def is_run_stale(run: ProviderImportRun) -> bool:
    if run.status != "running" or not run.started_at:
        return False
    started = run.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - started > timedelta(hours=STALE_RUN_HOURS)


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
    phase = run.phase or ("importing" if run.discovered else "discovering")
    if run.status in ("completed", "failed"):
        phase = run.phase or run.status
    return {
        "run_id": run.run_id,
        "provider": run.provider,
        "status": run.status,
        "phase": phase,
        "progress_detail": run.progress_detail,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "discovered": run.discovered,
        "created": run.created,
        "skipped": run.skipped,
        "failed": run.failed,
        "processed": processed,
        "triggered_by": run.triggered_by,
        "is_stale": is_run_stale(run),
        "failed_items": [
            {
                "source_url": item.source_url,
                "cod_product": item.cod_product,
                "error_message": item.error_message,
            }
            for item in failed_items
        ],
    }
