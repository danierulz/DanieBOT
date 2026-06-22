"""Re-export HOLIC catalog discovery for bulk CLI."""

from provider_importers.holic_catalog import discover_holic_product_urls

__all__ = ["discover_holic_product_urls"]
