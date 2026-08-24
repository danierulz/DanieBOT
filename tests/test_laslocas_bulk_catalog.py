import unittest
from unittest.mock import MagicMock, patch

from provider_importers.bulk.laslocas_catalog import (
    extract_ficha_urls,
    get_laslocas_category,
    listing_url_for_category,
    load_laslocas_categories,
)


LISTING_HTML = """
<html><body>
  <div id="pag">
    <a href="/productos/denim?page=2">2</a>
    <a href="/productos/denim?page=3">3</a>
  </div>
  <a href="/ficha-1-test-a">A</a>
  <a href="https://laslocas.com/ficha-2-test-b">B</a>
</body></html>
"""


class LasLocasBulkCatalogTest(unittest.TestCase):
    def test_categories_file_loads(self):
        categories = load_laslocas_categories()
        self.assertGreaterEqual(len(categories), 10)
        self.assertEqual(get_laslocas_category("denim")["listing_path"], "/productos/jean")

    def test_listing_url_for_category(self):
        category = get_laslocas_category("denim")
        self.assertEqual(
            listing_url_for_category(category, page=1),
            "https://laslocas.com/productos/jean",
        )
        self.assertEqual(
            listing_url_for_category(category, page=2),
            "https://laslocas.com/productos/jean?page=2",
        )
        self.assertEqual(
            listing_url_for_category(category, page=1, ajax=True),
            "https://laslocas.com/productos/jean?page=1&ajax=1",
        )

    def test_extract_ficha_urls(self):
        urls = extract_ficha_urls(LISTING_HTML, "https://laslocas.com/productos/denim")
        self.assertEqual(
            urls,
            [
                "https://laslocas.com/ficha-1-test-a",
                "https://laslocas.com/ficha-2-test-b",
            ],
        )

    @patch("provider_importers.bulk.laslocas_catalog.load_laslocas_categories")
    @patch("provider_importers.bulk.laslocas_catalog._discover_category_urls")
    def test_discover_all_categories_deduplicates(self, mock_discover, mock_load):
        from provider_importers.bulk.laslocas_catalog import discover_laslocas_product_urls

        mock_load.return_value = [
            {"id": "a", "listing_path": "/productos/a"},
            {"id": "b", "listing_path": "/productos/b"},
        ]
        mock_discover.side_effect = [
            ["https://laslocas.com/ficha-1"],
            ["https://laslocas.com/ficha-1", "https://laslocas.com/ficha-2"],
        ]
        session = MagicMock()
        urls = discover_laslocas_product_urls(session, all_categories=True)
        self.assertEqual(urls, ["https://laslocas.com/ficha-1", "https://laslocas.com/ficha-2"])
        self.assertEqual(mock_discover.call_count, 2)

    def test_discover_uses_ajax_pages_until_empty(self):
        from provider_importers.bulk.laslocas_catalog import _discover_category_urls

        page1 = MagicMock()
        page1.status_code = 200
        page1.text = '<a href="/ficha-10-uno">Uno</a>'
        page1.url = "https://laslocas.com/productos/jean/chupin/?page=1&ajax=1"
        page2 = MagicMock()
        page2.status_code = 200
        page2.text = "\n"
        page2.url = "https://laslocas.com/productos/jean/chupin/?page=2&ajax=1"
        session = MagicMock()
        session.get.side_effect = [page1, page2]
        urls = _discover_category_urls(
            session,
            {"id": "chupin", "name": "CHUPIN", "listing_path": "/productos/jean/chupin"},
            max_pages=0,
        )
        self.assertEqual(urls, ["https://laslocas.com/ficha-10-uno"])
        first_call_url = session.get.call_args_list[0].args[0]
        self.assertIn("ajax=1", first_call_url)


if __name__ == "__main__":
    unittest.main()
