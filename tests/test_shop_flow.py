import os
import unittest

os.environ.setdefault("SITE_PUBLIC_URL", "http://localhost:5000")

from whatsapp.conversation import get_welcome_reply
from whatsapp.shop_flow import CB_SHOP_START
from whatsapp import shop_flow
from whatsapp.shop_flow import (
    CB_SHOP_AGAIN,
    PREFIX_CAT,
    PREFIX_CAT_PAGE,
    PREFIX_SIZE,
    clear_session,
    handle_callback,
    handle_text,
    start_shop,
    start_with_category,
)


class ShopFlowUrlTest(unittest.TestCase):
    def setUp(self):
        shop_flow._sessions.clear()

    def test_finish_jeans_size_m(self):
        shop_flow._sessions["wa1"] = shop_flow.ShopSession(
            step=shop_flow.ShopStep.SIZE,
            category_slug="jeans",
            category_name="Jeans",
        )
        reply = handle_callback("wa1", f"{PREFIX_SIZE}M")
        self.assertIn("cat=jeans", reply.text)
        self.assertIn("size_code=M", reply.text)
        self.assertIsNone(shop_flow._sessions.get("wa1"))

    def test_finish_todos_all_sizes(self):
        shop_flow._sessions["wa1"] = shop_flow.ShopSession(
            step=shop_flow.ShopStep.SIZE,
            category_slug="todos",
            category_name="Ver todo",
        )
        reply = handle_callback("wa1", f"{PREFIX_SIZE}ALL")
        self.assertIn("cat=todos", reply.text)
        self.assertNotIn("size_code", reply.text)


class ShopFlowCategoryTest(unittest.TestCase):
    def setUp(self):
        shop_flow._sessions.clear()

    def test_start_shows_categories(self):
        reply = start_shop()
        self.assertIn("categoría", reply.text.lower())
        self.assertGreaterEqual(len(reply.buttons), 1)
        self.assertLessEqual(len(reply.buttons), 3)

    def test_category_page_zero_has_next_or_categories(self):
        reply = handle_callback("wa1", f"{PREFIX_CAT_PAGE}0")
        titles = [b.title for b in reply.buttons]
        self.assertTrue(
            any("Siguiente" in t for t in titles)
            or any("Jean" in t or "Pantal" in t or "Remera" in t for t in titles)
        )

    def test_select_jeans_asks_size(self):
        reply = handle_callback("wa1", f"{PREFIX_CAT}jeans")
        self.assertIn("talle", reply.text.lower())
        self.assertEqual(shop_flow._sessions["wa1"].category_slug, "jeans")
        codes = [b.callback_data for b in reply.buttons]
        self.assertTrue(any(c.startswith(PREFIX_SIZE) for c in codes))

    def test_start_with_category_skips_to_size(self):
        reply = start_with_category("jeans")
        self.assertIn("Jeans", reply.text)
        self.assertIn("talle", reply.text.lower())


class ShopFlowTextTest(unittest.TestCase):
    def setUp(self):
        shop_flow._sessions.clear()

    def test_cancel_clears_session(self):
        handle_callback("wa1", f"{PREFIX_CAT}jeans")
        reply = handle_text("wa1", "cancelar", "Ana")
        self.assertIn("Ana", reply.text)
        self.assertNotIn("wa1", shop_flow._sessions)

    def test_type_size_during_session(self):
        handle_callback("wa1", f"{PREFIX_CAT}remeras")
        reply = handle_text("wa1", "XL", "")
        self.assertIn("size_code=XL", reply.text)
        self.assertIn("remeras", reply.text)

    def test_type_todos_during_session(self):
        handle_callback("wa1", f"{PREFIX_CAT}jeans")
        reply = handle_text("wa1", "todos", "")
        self.assertIn("cat=jeans", reply.text)
        self.assertNotIn("size_code", reply.text)


class WelcomeShopTest(unittest.TestCase):
    def test_welcome_has_ver_tienda(self):
        reply = get_welcome_reply("Lu")
        titles = [b.title for b in reply.buttons]
        self.assertIn("Ver tienda", titles)
        self.assertEqual(reply.buttons[0].callback_data, CB_SHOP_START)

    def test_shop_again_restarts(self):
        shop_flow._sessions.clear()
        reply = handle_callback("wa1", CB_SHOP_AGAIN)
        self.assertIn("categoría", reply.text.lower())


if __name__ == "__main__":
    unittest.main()
