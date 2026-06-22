import unittest
from unittest.mock import patch

import requests

from provider_importers.holic import ProviderImportError, fetch_holic_product, parse_holic_product
from provider_importers.registry import detect_provider


HOLIC_HTML = """
<html>
  <head>
    <meta name="description" content="Remera de ribb manga larga cuello tejido.">
    <meta property="og:image" content="https://holiclothing.com.ar/wp-content/uploads/fallback.jpg">
    <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@graph": [
          {
            "@type": "ItemPage",
            "name": "Remera 1971",
            "description": "Remera de ribb manga larga cuello tejido.",
            "image": {
              "@type": "ImageObject",
              "url": "https://holiclothing.com.ar/wp-content/uploads/main.jpg"
            }
          }
        ]
      }
    </script>
  </head>
  <body>
    <h1 class="product_title entry-title">Remera 1971</h1>
    <p class="price">
      <span class="woocommerce-Price-amount amount"><bdi><span class="woocommerce-Price-currencySymbol">$</span>9,400.00</bdi></span>
    </p>
    <div class="woocommerce-product-gallery__image">
      <a href="https://holiclothing.com.ar/wp-content/uploads/main.jpg">
        <img data-large_image="https://holiclothing.com.ar/wp-content/uploads/main.jpg">
      </a>
    </div>
    <div class="woocommerce-product-gallery__image">
      <a href="https://holiclothing.com.ar/wp-content/uploads/detail.jpg">
        <img data-large_image="https://holiclothing.com.ar/wp-content/uploads/detail.jpg">
      </a>
    </div>
    <span class="posted_in">
      <a href="https://holiclothing.com.ar/product-category/new-in/">New In</a>
      <a href="https://holiclothing.com.ar/product-category/remeras/">Remeras</a>
    </span>
    <span class="sku">R3846B-1</span>
    <div id="tab-description">Remera de ribb manga larga cuello tejido.</div>
    <div class="wd-swatches-product">
      <div class="wd-swatch" title="Azul Marino" aria-label="Azul Marino" data-value="azul-marino"></div>
      <div class="wd-swatch" title="Negro" aria-label="Negro" data-value="negro"></div>
      <div class="wd-swatch" title="Bordó" aria-label="Bordó" data-value="bordo"></div>
    </div>
    <select name="attribute_pa_color" id="pa_color">
      <option value="">Elige una opción</option>
      <option value="azul-marino">Azul Marino</option>
      <option value="negro">Negro</option>
    </select>
  </body>
</html>
"""


HOLIC_SALE_HTML = """
<html>
  <body>
    <h1 class="product_title entry-title">Remera Members</h1>
    <p class="price">
      <del><span class="woocommerce-Price-amount amount"><bdi><span class="woocommerce-Price-currencySymbol">$</span>7,600.00</bdi></span></del>
      <ins><span class="woocommerce-Price-amount amount"><bdi><span class="woocommerce-Price-currencySymbol">$</span>6,800.00</bdi></span></ins>
    </p>
    <span class="sku">R1234-1</span>
    <span class="posted_in">
      <a href="https://holiclothing.com.ar/product-category/remeras/">Remeras</a>
    </span>
  </body>
</html>
"""


class HolicImporterTest(unittest.TestCase):
    def test_parse_product_extracts_catalog_fields(self):
        product = parse_holic_product(
            HOLIC_HTML,
            "https://holiclothing.com.ar/product/remera-1971/",
        )

        self.assertEqual(product.provider, "holic")
        self.assertEqual(product.title, "Remera 1971")
        self.assertIsNone(product.sku)
        self.assertEqual(product.cod_product, "holic-r3846b-1-remera-1971")
        self.assertEqual(product.price, 9400)
        self.assertFalse(product.is_sale)
        self.assertEqual(product.category_slug, "remeras")
        self.assertEqual(product.colors, ["Azul Marino", "Negro", "Bordó"])
        self.assertIn("https://holiclothing.com.ar/wp-content/uploads/main.jpg", product.image_urls)

    def test_parse_sale_product(self):
        product = parse_holic_product(
            HOLIC_SALE_HTML,
            "https://holiclothing.com.ar/product/remera-members/",
        )
        self.assertEqual(product.price, 6800)
        self.assertEqual(product.original_price, 7600)
        self.assertTrue(product.is_sale)
        self.assertEqual(product.discount_percent, 11)

    def test_accepts_producto_url_path(self):
        product = parse_holic_product(
            HOLIC_HTML,
            "https://holiclothing.com.ar/producto/remera-1971/",
        )
        self.assertEqual(product.title, "Remera 1971")

    def test_rejects_non_holic_product_urls(self):
        with self.assertRaises(ProviderImportError):
            parse_holic_product(HOLIC_HTML, "https://example.com/product/x/")

    def test_detect_provider_recognizes_holic(self):
        self.assertEqual(
            detect_provider("https://holiclothing.com.ar/product/remera-1971/"),
            "holic",
        )

    def test_fetch_maps_rate_limit_to_provider_error(self):
        response = requests.Response()
        response.status_code = 429
        response._content = b"Too Many Requests"
        http_error = requests.HTTPError("429 Client Error", response=response)

        with patch("provider_importers.holic.requests.get", return_value=response):
            with patch.object(response, "raise_for_status", side_effect=http_error):
                with self.assertRaises(ProviderImportError) as ctx:
                    fetch_holic_product("https://holiclothing.com.ar/product/remera-1971/")

        self.assertEqual(ctx.exception.code, "rate_limit")
        self.assertIn("limitó las consultas", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
