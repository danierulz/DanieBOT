import os
import unittest

os.environ.setdefault("ORDER_CODE_PREFIX", "OJ")

from services.order_code import extract_order_code, generate_order_code


class OrderCodeTest(unittest.TestCase):
    def test_generate_format(self):
        code = generate_order_code()
        self.assertRegex(code, r"^OJ-\d{8}-[A-HJ-NP-Z2-9]{4}$")

    def test_extract_from_message(self):
        text = "Hola, Pedido OJ-20260519-8K4Q con detalle"
        self.assertEqual(extract_order_code(text), "OJ-20260519-8K4Q")

    def test_extract_none(self):
        self.assertIsNone(extract_order_code("sin codigo"))


if __name__ == "__main__":
    unittest.main()
