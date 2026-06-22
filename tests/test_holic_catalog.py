import unittest

from provider_importers.holic_catalog import (
    extract_product_urls_from_listing,
    normalize_holic_product_url,
)


CATALOG_HTML = """
<html>
  <body>
    <a href="https://holiclothing.com.ar/product/remera-1971/">Remera 1971</a>
    <a href="/product/conjunto-new-york/">Conjunto New York</a>
    <a href="https://holiclothing.com.ar/product-category/remeras/">Remeras</a>
    <a href="https://holiclothing.com.ar/product/remera-1971/?add-to-cart=123">Add to cart</a>
    <a href="/tienda/page/2/">Page 2</a>
  </body>
</html>
"""


class HolicCatalogTest(unittest.TestCase):
    def test_normalize_product_url(self):
        url = normalize_holic_product_url(
            "https://holiclothing.com.ar/product/remera-1971/?ref=1",
            "https://holiclothing.com.ar/tienda/",
        )
        self.assertEqual(url, "https://holiclothing.com.ar/product/remera-1971/")

    def test_normalize_rejects_category_links(self):
        self.assertIsNone(
            normalize_holic_product_url(
                "https://holiclothing.com.ar/product-category/remeras/",
                "https://holiclothing.com.ar/tienda/",
            )
        )

    def test_extract_product_urls_from_listing(self):
        urls = extract_product_urls_from_listing(
            CATALOG_HTML,
            "https://holiclothing.com.ar/tienda/",
        )
        self.assertIn("https://holiclothing.com.ar/product/remera-1971/", urls)
        self.assertIn("https://holiclothing.com.ar/product/conjunto-new-york/", urls)
        self.assertEqual(len(urls), 2)


if __name__ == "__main__":
    unittest.main()
