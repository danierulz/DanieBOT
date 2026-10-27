"""Re-export So Chic catalog discovery for the bulk CLI."""

from provider_importers.sochic_catalog import discover_sochic_product_urls

__all__ = ["discover_sochic_product_urls"]
