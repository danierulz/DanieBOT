import unittest

from services.product_activation import (
    NEED_CATEGORY,
    NEED_PRICE,
    NEED_STOCK,
    activation_blockers,
    format_activation_error,
    variant_is_sellable,
)


class ProductActivationRulesTest(unittest.TestCase):
    def test_sellable_with_stock_or_encargo(self):
        self.assertTrue(variant_is_sellable({"qty_stock_local": 1, "encargo_habilitado": False}))
        self.assertTrue(variant_is_sellable({"qty_stock_local": 0, "encargo_habilitado": True}))
        self.assertFalse(variant_is_sellable({"qty_stock_local": 0, "encargo_habilitado": False}))
        self.assertFalse(
            variant_is_sellable({"qty_stock_local": 2, "encargo_habilitado": True, "activo": False})
        )

    def test_blockers_for_color_only_product(self):
        blockers = activation_blockers(
            category_id=None,
            price=5000,
            variants=[{"qty_stock_local": 0, "encargo_habilitado": False, "color_id": 3}],
        )
        self.assertIn(NEED_CATEGORY, blockers)
        self.assertIn(NEED_STOCK, blockers)
        self.assertNotIn(NEED_PRICE, blockers)

    def test_ready_to_publish(self):
        blockers = activation_blockers(
            category_id=8,
            price=12000,
            variants=[{"qty_stock_local": 2, "encargo_habilitado": False, "size_code": "M"}],
        )
        self.assertEqual(blockers, [])
        self.assertEqual(format_activation_error(blockers), "")

    def test_error_message_joins_blockers(self):
        msg = format_activation_error([NEED_CATEGORY, NEED_STOCK])
        self.assertTrue(msg.startswith("No se puede activar:"))
        self.assertIn(NEED_CATEGORY, msg)
        self.assertIn(NEED_STOCK, msg)


if __name__ == "__main__":
    unittest.main()
