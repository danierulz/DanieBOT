import os
import unittest

os.environ.setdefault("SITE_PUBLIC_URL", "http://localhost:5000")
os.environ.setdefault("SITE_BRAND_NAME", "Outfit Jazmines Test")

from whatsapp.conversation import (
    CB_ASESOR,
    CB_ESTADO_PEDIDO,
    CB_JEANS,
    CB_MENU,
    CB_TALLES,
    Intent,
    detect_intent,
    get_jeans_catalog_url,
    get_welcome_reply,
    reply_for_callback,
    reply_for_intent,
    route_text_message,
)
from whatsapp.shop_flow import CB_SHOP_START


class DetectIntentTest(unittest.TestCase):
    def test_jeans_keywords(self):
        for msg in ("quiero jeans", "tienen jean?", "busco denim"):
            self.assertEqual(detect_intent(msg), Intent.JEANS, msg)

    def test_sizes_keywords(self):
        self.assertEqual(detect_intent("que talles tienen"), Intent.SIZES)

    def test_shipping_keywords(self):
        self.assertEqual(detect_intent("cuanto sale el envio"), Intent.SHIPPING)

    def test_stores_keywords(self):
        self.assertEqual(detect_intent("donde retiro"), Intent.STORES)

    def test_advisor_keywords(self):
        self.assertEqual(detect_intent("quiero hablar con un asesor"), Intent.ADVISOR)

    def test_greeting(self):
        self.assertEqual(detect_intent("hola buenas"), Intent.GREETING)

    def test_unknown_goes_to_help(self):
        self.assertEqual(detect_intent("xyz random"), Intent.HELP)


class JeansCatalogUrlTest(unittest.TestCase):
    def test_jeans_url_has_cat_param(self):
        self.assertIn("cat=jeans", get_jeans_catalog_url())
        self.assertTrue(get_jeans_catalog_url().startswith("http://localhost:5000"))


class WelcomeReplyTest(unittest.TestCase):
    def test_welcome_has_ver_tienda(self):
        reply = get_welcome_reply("María")
        self.assertIn("María", reply.text)
        self.assertEqual(len(reply.buttons), 3)
        titles = [b.title for b in reply.buttons]
        self.assertIn("Ver tienda", titles)
        self.assertEqual(reply.buttons[0].callback_data, CB_SHOP_START)

    def test_welcome_mentions_promo_or_pedido(self):
        reply = get_welcome_reply("Ana")
        self.assertTrue(
            "pedido" in reply.text.lower() or "compra" in reply.text.lower()
        )


class ReplyForIntentTest(unittest.TestCase):
    def test_jeans_reply_asks_size(self):
        reply = reply_for_intent(Intent.JEANS, "Lu")
        self.assertIn("talle", reply.text.lower())

    def test_sizes_reply_lists_standard_sizes(self):
        reply = reply_for_intent(Intent.SIZES)
        self.assertIn("XS", reply.text)
        self.assertIn("XXL", reply.text)

    def test_shipping_reply_mentions_minimum(self):
        reply = reply_for_intent(Intent.SHIPPING)
        self.assertIn("100.000", reply.text)

    def test_stores_reply_lists_both_locations(self):
        reply = reply_for_intent(Intent.STORES)
        self.assertIn("José C. Paz", reply.text)
        self.assertIn("Nogués", reply.text)

    def test_help_offers_ver_tienda(self):
        reply = reply_for_intent(Intent.HELP)
        self.assertIn("Ver tienda", [b.title for b in reply.buttons])


class RouteTextTest(unittest.TestCase):
    def test_route_hola_is_welcome(self):
        reply = route_text_message("hola", "Cami")
        self.assertIn("Cami", reply.text)
        self.assertEqual(reply.buttons[0].callback_data, CB_SHOP_START)

    def test_route_jeans_with_wa_id_starts_shop(self):
        reply = route_text_message("mostrame jeans", wa_id="wa99")
        self.assertIn("talle", reply.text.lower())

    def test_route_catalog_with_wa_id_starts_categories(self):
        reply = route_text_message("ver catalogo", wa_id="wa99")
        self.assertIn("categoría", reply.text.lower())


class CallbackReplyTest(unittest.TestCase):
    def test_jeans_button(self):
        reply = reply_for_callback(CB_JEANS)
        self.assertIn("cat=jeans", reply.text)

    def test_menu_button_has_catalog_and_pedido(self):
        reply = reply_for_callback(CB_MENU)
        self.assertIn("cat=todos", reply.text)
        self.assertIn("código", reply.text.lower())

    def test_estado_pedido_mentions_code_format(self):
        reply = reply_for_callback(CB_ESTADO_PEDIDO)
        self.assertIn("OJ-", reply.text)

    def test_asesor_button(self):
        reply = reply_for_callback(CB_ASESOR)
        self.assertIn("asesor", reply.text.lower())

    def test_talles_button_same_as_intent(self):
        from_btn = reply_for_callback(CB_TALLES)
        from_intent = reply_for_intent(Intent.SIZES)
        self.assertEqual(from_btn.text, from_intent.text)


if __name__ == "__main__":
    unittest.main()
