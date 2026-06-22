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


@dataclass
class BulkImportSummary:
    provider: str
    discovered: int = 0
    created: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "discovered": self.discovered,
            "created": self.created,
            "skipped": self.skipped,
            "failed": self.failed,
            "processed": self.created + self.skipped + self.failed,
            "errors": self.errors,
        }
