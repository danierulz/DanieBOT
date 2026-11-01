"""Admin entry for the local provider watch. Does not import or schedule."""

from __future__ import annotations

import time
from typing import Callable

from sqlalchemy.orm import Session

from provider_importers.bulk.existing import load_dedup_index
from provider_importers.bulk.watch import (
    WatchNotLocalError,
    WatchRequestError,
    local_watch_block_reason,
    normalize_watch_limit,
    normalize_watch_providers,
    scan_watch,
)
from provider_importers.bulk.watch_listings import ListingPage
from provider_importers.types import ProviderImportError

__all__ = [
    "WatchNotLocalError",
    "WatchRequestError",
    "run_provider_watch",
]


def run_provider_watch(
    db: Session,
    *,
    providers: list[str] | None,
    limit: int,
    laslocas_category: str | None,
    fetch: Callable[..., ListingPage] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> dict:
    """Read dedup keys and the first listing page. No insert, no cron."""
    blocked = local_watch_block_reason()
    if blocked:
        raise WatchNotLocalError(blocked)

    chosen = normalize_watch_providers(providers)
    capped = normalize_watch_limit(limit)
    # Kept for API/CLI compat; listing URLs no longer depend on category.
    category = (laslocas_category or "denim").strip() or "denim"

    report = scan_watch(
        providers=chosen,
        limit=capped,
        index=load_dedup_index(db),
        laslocas_category=category,
        fetch=fetch,
        sleep=sleep if sleep is not None else time.sleep,
    )
    return report.to_dict()
