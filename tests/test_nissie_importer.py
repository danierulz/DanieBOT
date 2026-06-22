import unittest
from unittest.mock import patch

from provider_importers.nissie import (
    ProviderImportError,
    fetch_nissie_product,
    parse_nissie_product,
)
from provider_importers.registry import detect_provider


NISSIE_DENIM_HTML = """
<html>
  <head>
    <meta name="description" content="Denim elastizado, color azul clásico. Bien de talle.">
    <meta property="og:image" content="https://dcdn-us.mitiendanube.com/stores/001/059/324/products/denim-main-640-0.webp">
  </head>
  <body>
    <h1>Denim Blue</h1>
    <div class="js-price-display">$24.000</div>
    <div class="js-product-slide">
      <img src="//dcdn-us.mitiendanube.com/stores/001/059/324/products/denim-main-480-0.webp">
    </div>
    <div class="swiper-slide">
      <img src="//dcdn-us.mitiendanube.com/stores/001/059/324/products/denim-alt-240-0.webp">
    </div>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org/",
        "@type": "WebPage",
        "breadcrumb": {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Inicio", "item": "https://nissiedenim.com.ar"},
                {"@type": "ListItem", "position": 2, "name": "WOMEN", "item": "https://nissiedenim.com.ar/women1/"},
                {"@type": "ListItem", "position": 3, "name": "ELASTIZADOS", "item": "https://nissiedenim.com.ar/women1/jeans/"},
                {"@type": "ListItem", "position": 4, "name": "Denim Blue", "item": "https://nissiedenim.com.ar/productos/denim-blue/"}
            ]
        },
        "mainEntity": {
            "@type": "ProductGroup",
            "name": "Denim Blue",
            "description": "Denim elastizado, color azul clásico. Bien de talle.",
            "productGroupID": "282540155",
            "hasVariant": [
                {
                    "@type": "Product",
                    "size": "36",
                    "offers": {"@type": "Offer", "price": "24000", "priceCurrency": "ARS"}
                },
                {
                    "@type": "Product",
                    "size": "38",
                    "offers": {"@type": "Offer", "price": "24000", "priceCurrency": "ARS"}
                }
            ]
        }
    }
    </script>
  </body>
</html>
"""

NISSIE_REMERA_HTML = """
<html>
  <body>
    <h1>Remera Paradise</h1>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org/",
        "@type": "WebPage",
        "mainEntity": {
            "@type": "ProductGroup",
            "name": "Remera Paradise",
            "description": "Remera de morley, con estampa. SIN CAMBIO.",
            "productGroupID": "309524005",
            "hasVariant": [
                {
                    "@type": "Product",
                    "size": "S",
                    "color": "Rosa Viejo",
                    "offers": {"@type": "Offer", "price": "11000", "priceCurrency": "ARS"}
                },
                {
                    "@type": "Product",
                    "size": "M",
                    "color": "Negro",
                    "offers": {"@type": "Offer", "price": "11000", "priceCurrency": "ARS"}
                }
            ]
        }
    }
    </script>
  </body>
</html>
"""


class NissieImporterTest(unittest.TestCase):
    def test_parse_denim_product(self):
        product = parse_nissie_product(
            NISSIE_DENIM_HTML,
            "https://nissiedenim.com.ar/productos/denim-blue/",
        )
        self.assertEqual(product.provider, "nissie")
        self.assertEqual(product.title, "Denim Blue")
        self.assertEqual(product.price, 24000)
        self.assertEqual(product.sku, 282540155)
        self.assertEqual(product.cod_product, "nissie-282540155")
        self.assertEqual(product.category_slug, "jeans")
        self.assertEqual(product.colors, [])
        self.assertIn("640-0.webp", product.image_urls[0])
        self.assertTrue(any("denim-alt" in url for url in product.image_urls))

    def test_parse_remera_extracts_colors(self):
        product = parse_nissie_product(
            NISSIE_REMERA_HTML,
            "https://nissiedenim.com.ar/productos/remera-paradise-kh5fx/",
        )
        self.assertEqual(product.price, 11000)
        self.assertEqual(product.colors, ["Rosa Viejo", "Negro"])

    def test_rejects_non_nissie_urls(self):
        with self.assertRaises(ProviderImportError):
            parse_nissie_product(NISSIE_DENIM_HTML, "https://example.com/productos/x/")

    def test_detect_provider_nissie(self):
        self.assertEqual(
            detect_provider("https://nissiedenim.com.ar/productos/denim-blue/"),
            "nissie",
        )

    @patch("provider_importers.nissie.requests.get")
    def test_fetch_nissie_product(self, mock_get):
        response = mock_get.return_value
        response.raise_for_status.return_value = None
        response.text = NISSIE_DENIM_HTML
        response.url = "https://nissiedenim.com.ar/productos/denim-blue/"

        product = fetch_nissie_product("https://nissiedenim.com.ar/productos/denim-blue/")
        self.assertEqual(product.provider, "nissie")
        self.assertEqual(product.title, "Denim Blue")


if __name__ == "__main__":
    unittest.main()
