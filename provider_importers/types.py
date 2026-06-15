from dataclasses import dataclass, field
from typing import Optional


class ProviderImportError(ValueError):
    """Raised when a provider page cannot be imported safely."""

    def __init__(self, message: str, *, code: str = "import_failed"):
        super().__init__(message)
        self.code = code


@dataclass
class ImportedProduct:
    provider: str
    source_url: str
    title: str
    description: str
    price: int
    cod_product: str
    sku: Optional[int] = None
    image_urls: list[str] = field(default_factory=list)
    image_assets: list[tuple[str, bytes]] = field(default_factory=list)
    category_slug: Optional[str] = None
    colors: list[str] = field(default_factory=list)
    is_sale: bool = False
    original_price: Optional[int] = None
    discount_percent: Optional[int] = None
    page_ficha: Optional[str] = None
