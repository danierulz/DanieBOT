import os
import unittest

os.environ.setdefault("SITE_PUBLIC_URL", "http://localhost:5000")

from config import get_site_public_url
from services.catalog_urls import build_catalog_url


class BuildCatalogUrlTest(unittest.TestCase):
    @property
    def base(self) -> str:
        return get_site_public_url()

    def test_jeans_and_numeric_size(self):
        url = build_catalog_url("jeans", "38")
        self.assertIn("cat=jeans", url)
        self.assertIn("size_code=38", url)
        self.assertTrue(url.startswith(f"{self.base}/?"))

    def test_jeans_and_letter_size(self):
        url = build_catalog_url("jeans", "M")
        self.assertIn("cat=jeans", url)
        self.assertIn("size_code=M", url)

    def test_todos_without_size(self):
        url = build_catalog_url("todos", None)
        self.assertIn("cat=todos", url)
        self.assertNotIn("size_code", url)

    def test_all_size_omits_param(self):
        url = build_catalog_url("jeans", "ALL")
        self.assertIn("cat=jeans", url)
        self.assertNotIn("size_code", url)

    def test_no_filters(self):
        url = build_catalog_url(None, None)
        self.assertEqual(url, f"{self.base}/")


if __name__ == "__main__":
    unittest.main()
