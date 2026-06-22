import unittest

from provider_importers.nissie_catalog import (
    extract_product_urls_from_listing,
    normalize_nissie_product_url,
)


CATALOG_HTML = """
<html>
  <body>
    <a href="/productos/denim-blue/">Denim Blue</a>
    <a href="https://nissiedenim.com.ar/productos/remera-paradise-kh5fx/?variant=1">Remera</a>
    <a href="/women1/jeans/">Categoria</a>
    <script type="application/ld+json">
    {
        "@type": "Product",
        "mainEntityOfPage": {"@id": "https://nissiedenim.com.ar/productos/top-tiritas/"}
    }
    </script>
  </body>
</html>
"""


class NissieCatalogTest(unittest.TestCase):
    def test_normalize_product_url_strips_variant(self):
        url = normalize_nissie_product_url(
            "https://nissiedenim.com.ar/productos/denim-blue/?variant=123",
            "https://nissiedenim.com.ar/productos/",
        )
        self.assertEqual(url, "https://nissiedenim.com.ar/productos/denim-blue/")

    def test_extract_product_urls_from_listing(self):
        urls = extract_product_urls_from_listing(
            CATALOG_HTML,
            "https://nissiedenim.com.ar/productos/",
        )
        self.assertIn("https://nissiedenim.com.ar/productos/denim-blue/", urls)
        self.assertIn("https://nissiedenim.com.ar/productos/remera-paradise-kh5fx/", urls)
        self.assertIn("https://nissiedenim.com.ar/productos/top-tiritas/", urls)
        self.assertEqual(len(urls), 3)


if __name__ == "__main__":
    unittest.main()
