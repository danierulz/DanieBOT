import os
import unittest

os.environ.setdefault("SITE_BRAND_NAME", "Outfit Jazmines Test")

from config import get_order_confirmation_reply


class OrderConfirmationReplyTest(unittest.TestCase):
    def test_includes_thanks_and_preparing(self):
        text = get_order_confirmation_reply("María", "*Pedido OJ-20260522-ABCD*\nTotal: $100")
        self.assertIn("María", text)
        self.assertIn("gracias por comprar", text.lower())
        self.assertIn("preparando", text.lower())
        self.assertIn("OJ-20260522-ABCD", text)

    def test_without_name(self):
        text = get_order_confirmation_reply(None, "resumen")
        self.assertIn("Gracias por comprar", text)


if __name__ == "__main__":
    unittest.main()
