"""Types for bulk provider import."""

from __future__ import annotations

from dataclasses import dataclass, field

from provider_importers.bulk.delays import REQUEST_DELAY_MS


@dataclass
class BulkImportOptions:
    provider: str
    dry_run: bool = False
    delay_ms: int = REQUEST_DELAY_MS
    category_id: str | None = None
    all_categories: bool = False
    max_pages: int = 0
    status: bool = False
    import_category_id: int | None = None
    size_code: str = "UNICO"
    urls: list[str] = field(default_factory=list)
    limit: int = 0
    skip_existing: bool = True
    price_markup_percent: float = 0.0
    rate_limit_retries: int = 3
    rate_limit_backoff_seconds: float = 15.0
    rate_limit_max_backoff_seconds: float = 120.0
    rate_limit_cooldown_seconds: int = 600
    rate_limit_hard_stop: bool = False


@dataclass
class BulkImportSummary:
    provider: str
    discovered: int = 0
    created: int = 0
    skipped: int = 0
    failed: int = 0
    skipped_existing: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)
    rate_limited: bool = False
    cooldown_hint_seconds: int = 0
    aborted_remaining: int = 0
    stopped_during: str = ""
    rate_limit_attempts: int = 0

    def to_dict(self) -> dict:
        payload = {
            "provider": self.provider,
            "discovered": self.discovered,
            "created": self.created,
            "skipped": self.skipped,
            "skipped_existing": self.skipped_existing,
            "failed": self.failed,
            "processed": self.created + self.skipped + self.failed,
            "errors": self.errors,
            "rate_limited": self.rate_limited,
            "cooldown_hint_seconds": self.cooldown_hint_seconds,
            "aborted_remaining": self.aborted_remaining,
        }
        if self.rate_limited:
            payload["stopped_during"] = self.stopped_during
            payload["rate_limit_attempts"] = self.rate_limit_attempts
        return payload
