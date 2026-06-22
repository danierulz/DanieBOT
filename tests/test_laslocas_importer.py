import unittest
from unittest.mock import MagicMock, patch

from provider_importers.laslocas import (
    ProviderImportError,
    _build_login_payload,
    parse_laslocas_product,
    fetch_laslocas_product,
)
from bs4 import BeautifulSoup
from provider_importers.registry import detect_provider


LASLOCAS_HTML = """
<html>
  <body>
    <span id="codProd">BSPOR</span>
    <h1 class="item-title inline">BLUE SPORTY</h1>
    <script type="application/ld+json">
      {
        "@type": "Product",
        "sku": "224",
        "name": "Blue Sporty",
        "description": "Jogger denim",
        "offers": {"price": "12500", "priceCurrency": "ARS"}
      }
    </script>
    <motion.div class="d2">
      <a href="https://laslocas.com/media/foto1.jpg"></a>
      <a href="https://laslocas.com/media/foto2.jpg"></a>
    </motion.div>
  </body>
</html>
"""

LASLOCAS_HTML_MULTILINE_JSONLD = """
<html>
  <body>
    <span id="codProd">BRANDY</span>
    <h1 class="item-title inline">CLÁSICO BRANDY</h1>
    <script type="application/ld+json">
      {
        "@type": "Product",
        "sku": "3317",
        "name": "CLÁSICO BRANDY",
        "description": "linea uno
linea dos",
        "offers": {"price": "28400.00", "priceCurrency": "ARS"}
      }
    </script>
  </body>
</html>
"""

LASLOCAS_HTML_PRICE_FALLBACK = """
<html>
  <body>
    <span id="codProd">BRANDY</span>
    <h1 class="item-title inline">CLÁSICO BRANDY</h1>
    <div class="item-price">$28.400</div>
  </body>
</html>
"""


LOGIN_FORM_HTML = """
<form method="post">
  <input type="email" id="inputEmail" name="_username" value="">
  <input type="password" id="inputPassword" name="_password" value="">
  <input type="hidden" name="_csrf_token" value="token123">
  <input type="hidden" name="_target_path" value="/">
  <input type="hidden" name="tipoPrecio" value="MIN">
</form>
"""


class LasLocasImporterTest(unittest.TestCase):
    def test_build_login_payload_uses_form_field_names(self):
        form = BeautifulSoup(LOGIN_FORM_HTML, "html.parser").find("form")
        payload = _build_login_payload(form, "a@b.com", "secret")
        self.assertEqual(payload["_username"], "a@b.com")
        self.assertEqual(payload["_password"], "secret")
        self.assertEqual(payload["_csrf_token"], "token123")
        self.assertEqual(payload["tipoPrecio"], "MIN")

    def test_parse_product_extracts_catalog_fields(self):
        product = parse_laslocas_product(
            LASLOCAS_HTML,
            "https://laslocas.com/ficha-224-jogger-blue-sporty",
        )

        self.assertEqual(product.provider, "laslocas")
        self.assertEqual(product.cod_product, "BSPOR")
        self.assertEqual(product.title, "BLUE SPORTY")
        self.assertEqual(product.sku, 224)
        self.assertEqual(product.price, 12500)
        self.assertEqual(product.page_ficha, "ficha-224-jogger-blue-sporty")
        self.assertGreaterEqual(len(product.image_urls), 1)

    def test_parse_product_handles_multiline_jsonld_description(self):
        product = parse_laslocas_product(
            LASLOCAS_HTML_MULTILINE_JSONLD,
            "https://laslocas.com/ficha-3317-clasico-brandy",
        )
        self.assertEqual(product.sku, 3317)
        self.assertEqual(product.price, 28400)

    def test_parse_product_falls_back_to_html_price(self):
        product = parse_laslocas_product(
            LASLOCAS_HTML_PRICE_FALLBACK,
            "https://laslocas.com/ficha-3317-clasico-brandy",
        )
        self.assertEqual(product.price, 28400)

    def test_rejects_non_ficha_urls(self):
        with self.assertRaises(ProviderImportError):
            parse_laslocas_product(LASLOCAS_HTML, "https://laslocas.com/login")

    def test_detect_provider(self):
        self.assertEqual(
            detect_provider("https://sochic.com.ar/product/x/"),
            "sochic",
        )
        self.assertEqual(
            detect_provider("https://laslocas.com/ficha-1-test"),
            "laslocas",
        )

    @patch("provider_importers.laslocas._download_gallery_images")
    @patch("provider_importers.laslocas._authenticated_session")
    def test_fetch_downloads_images(self, mock_session_factory, mock_download):
        session = MagicMock()
        response = MagicMock()
        response.text = LASLOCAS_HTML
        response.url = "https://laslocas.com/ficha-224-jogger-blue-sporty"
        response.raise_for_status = MagicMock()
        session.get.return_value = response
        mock_session_factory.return_value = session
        mock_download.return_value = [("foto1.jpg", b"abc")]

        product = fetch_laslocas_product("https://laslocas.com/ficha-224-jogger-blue-sporty")
        self.assertEqual(product.provider, "laslocas")
        self.assertEqual(len(product.image_assets), 1)
        self.assertEqual(product.image_urls, [])


if __name__ == "__main__":
    unittest.main()
