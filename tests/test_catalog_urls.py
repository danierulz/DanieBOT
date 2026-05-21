import os
import unittest

os.environ.setdefault("SITE_PUBLIC_URL", "http://localhost:5000")

from services.catalog_urls import build_catalog_url


class BuildCatalogUrlTest(unittest.TestCase):
    def test_jeans_and_size(self):
        url = build_catalog_url("jeans", "M")
        self.assertIn("cat=jeans", url)
        self.assertIn("size_code=M", url)
        self.assertTrue(url.startswith("http://localhost:5000/?"))

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
        self.assertEqual(url, "http://localhost:5000/")


if __name__ == "__main__":
    unittest.main()
