import unittest

from provider_importers.sochic import ProviderImportError, parse_sochic_product


SOCHIC_HTML = """
<html>
  <head>
    <meta property="og:image" content="https://sochic.com.ar/fallback.jpg">
    <script type="application/ld+json">
      {
        "@context": "https://schema.org/",
        "@graph": [
          {
            "@type": "Product",
            "name": "Campera Friza Young Leaders",
            "description": "MEDIDAS\\nCONTORNO PECHO: 58",
            "image": "https://sochic.com.ar/wp-content/uploads/main.jpeg",
            "sku": "3515",
            "offers": [{"@type": "Offer", "price": "29000"}]
          }
        ]
      }
    </script>
  </head>
  <body>
    <h1 class="product_title entry-title">Campera Friza Young Leaders</h1>
    <p class="price">
      <del><span class="amount"><bdi>$29.000</bdi></span></del>
      <ins><span class="amount"><bdi>$26.100</bdi></span></ins>
    </p>
    <div class="woocommerce-product-gallery__image">
      <a href="https://sochic.com.ar/wp-content/uploads/main.jpeg">
        <img data-large_image="https://sochic.com.ar/wp-content/uploads/main.jpeg">
      </a>
    </div>
    <div class="woocommerce-product-gallery__image">
      <a href="https://sochic.com.ar/wp-content/uploads/detail.jpeg">
        <img data-large_image="https://sochic.com.ar/wp-content/uploads/detail.jpeg">
      </a>
    </div>
    <span class="posted_in">
      <a href="https://sochic.com.ar/product-category/camperas/">ABRIGOS</a>
      <a href="https://sochic.com.ar/product-category/ver-todo/">Ver Todo</a>
    </span>
    <table class="table vartable">
      <thead><tr><th>SKU</th><th>Stock</th><th>Color</th></tr></thead>
      <tbody>
        <tr><td>3515</td><td>Hay stock</td><td>Celeste</td></tr>
        <tr><td>3515</td><td>Hay stock</td><td>Rosa</td></tr>
      </tbody>
    </table>
  </body>
</html>
"""


class SoChicImporterTest(unittest.TestCase):
    def test_parse_product_extracts_catalog_fields(self):
        product = parse_sochic_product(
            SOCHIC_HTML,
            "https://sochic.com.ar/product/campera-friza-young-leaders/",
        )

        self.assertEqual(product.title, "Campera Friza Young Leaders")
        self.assertEqual(product.sku, 3515)
        self.assertEqual(product.cod_product, "sochic-3515-campera-friza-young-leaders")
        self.assertEqual(product.price, 26100)
        self.assertEqual(product.original_price, 29000)
        self.assertEqual(product.discount_percent, 10)
        self.assertEqual(product.category_slug, "camperas")
        self.assertEqual(product.colors, ["Celeste", "Rosa"])
        self.assertEqual(
            product.image_urls,
            [
                "https://sochic.com.ar/wp-content/uploads/main.jpeg",
                "https://sochic.com.ar/wp-content/uploads/detail.jpeg",
                "https://sochic.com.ar/fallback.jpg",
            ],
        )

    def test_rejects_non_sochic_product_urls(self):
        with self.assertRaises(ProviderImportError):
            parse_sochic_product(SOCHIC_HTML, "https://example.com/product/x/")


if __name__ == "__main__":
    unittest.main()
