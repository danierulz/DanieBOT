import unittest
from unittest.mock import MagicMock, patch

from provider_importers.sochic_catalog import (
    discover_sochic_product_urls,
    extract_product_urls_from_listing,
    normalize_sochic_product_url,
)
from provider_importers.types import ProviderImportError


CATALOG_HTML = """
<html><body>
  <a href="https://sochic.com.ar/product/campera-friza/">Campera</a>
  <a href="/product/top-morley/">Top</a>
  <a href="https://www.sochic.com.ar/product/campera-friza/?add-to-cart=9">dup</a>
  <a href="https://sochic.com.ar/product-category/camperas/">Camperas</a>
  <a href="https://sochic.com.ar/shop/">Shop</a>
  <a href="/shop/page/2/">2</a>
</body></html>
"""

PAGE_TWO = """
<html><body>
  <a href="/product/pollera-satin/">Pollera</a>
</body></html>
"""


class SochicCatalogTest(unittest.TestCase):
    def test_normalize_product_url(self):
        url = normalize_sochic_product_url(
            "https://www.sochic.com.ar/product/campera-friza/?ref=1",
            "https://sochic.com.ar/shop/",
        )
        self.assertEqual(url, "https://sochic.com.ar/product/campera-friza/")

    def test_normalize_rejects_category_and_shop(self):
        self.assertIsNone(
            normalize_sochic_product_url(
                "https://sochic.com.ar/product-category/camperas/",
                "https://sochic.com.ar/shop/",
            )
        )
        self.assertIsNone(
            normalize_sochic_product_url(
                "https://sochic.com.ar/shop/page/2/",
                "https://sochic.com.ar/shop/",
            )
        )

    def test_extract_product_urls_from_listing(self):
        urls = extract_product_urls_from_listing(CATALOG_HTML, "https://sochic.com.ar/shop/")
        self.assertEqual(
            urls,
            [
                "https://sochic.com.ar/product/campera-friza/",
                "https://sochic.com.ar/product/top-morley/",
            ],
        )

    def test_discover_paginates_then_stops(self):
        session = MagicMock()
        session.headers = {}
        page1 = MagicMock(status_code=200, text=CATALOG_HTML, url="https://sochic.com.ar/shop/")
        page1.raise_for_status = MagicMock()
        page2 = MagicMock(status_code=200, text=PAGE_TWO, url="https://sochic.com.ar/shop/page/2/")
        page2.raise_for_status = MagicMock()
        page3 = MagicMock(status_code=404, text="", url="https://sochic.com.ar/shop/page/3/")
        page3.raise_for_status.side_effect = __import__("requests").HTTPError("404")
        session.get.side_effect = [page1, page2, page3]

        with patch("provider_importers.sochic_catalog.time.sleep") as sleep:
            urls = discover_sochic_product_urls(session, max_pages=5)

        self.assertEqual(
            urls,
            [
                "https://sochic.com.ar/product/campera-friza/",
                "https://sochic.com.ar/product/top-morley/",
                "https://sochic.com.ar/product/pollera-satin/",
            ],
        )
        self.assertEqual(session.get.call_count, 3)
        sleep.assert_called()
        self.assertEqual(
            session.get.call_args_list[0].args[0],
            "https://sochic.com.ar/shop/",
        )
        self.assertEqual(
            session.get.call_args_list[1].args[0],
            "https://sochic.com.ar/shop/page/2/",
        )

    def test_category_and_max_pages(self):
        session = MagicMock()
        session.headers = {}
        page = MagicMock(status_code=200, text=CATALOG_HTML, url="https://sochic.com.ar/product-category/camperas/")
        page.raise_for_status = MagicMock()
        session.get.return_value = page

        urls = discover_sochic_product_urls(session, category_slug="Camperas", max_pages=1)
        self.assertEqual(session.get.call_count, 1)
        self.assertEqual(
            session.get.call_args.args[0],
            "https://sochic.com.ar/product-category/camperas/",
        )
        self.assertEqual(len(urls), 2)

    def test_invalid_category_slug(self):
        with self.assertRaises(ProviderImportError):
            discover_sochic_product_urls(MagicMock(), category_slug="../shop")


if __name__ == "__main__":
    unittest.main()
