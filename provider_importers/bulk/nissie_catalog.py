"""Re-export Nissie catalog discovery for bulk CLI."""

from provider_importers.nissie_catalog import discover_nissie_product_urls

__all__ = ["discover_nissie_product_urls"]
