"""Unit tests for product lifecycle draft/active/retired."""

import unittest
from types import SimpleNamespace

from services.product_lifecycle import (
    LIFECYCLE_ACTIVE,
    LIFECYCLE_DRAFT,
    LIFECYCLE_RETIRED,
    apply_lifecycle,
    apply_status_bool,
    lifecycle_of,
)


class ProductLifecycleTest(unittest.TestCase):
    def test_apply_lifecycle_syncs_status(self):
        product = SimpleNamespace(status=False, lifecycle=None)
        apply_lifecycle(product, LIFECYCLE_ACTIVE)
        self.assertTrue(product.status)
        self.assertEqual(product.lifecycle, LIFECYCLE_ACTIVE)
        apply_lifecycle(product, LIFECYCLE_DRAFT)
        self.assertFalse(product.status)
        self.assertEqual(product.lifecycle, LIFECYCLE_DRAFT)

    def test_uncheck_active_becomes_retired(self):
        product = SimpleNamespace(status=True, lifecycle=LIFECYCLE_ACTIVE)
        apply_status_bool(product, False)
        self.assertEqual(product.lifecycle, LIFECYCLE_RETIRED)
        self.assertFalse(product.status)

    def test_uncheck_draft_stays_draft(self):
        product = SimpleNamespace(status=False, lifecycle=LIFECYCLE_DRAFT)
        apply_status_bool(product, False)
        self.assertEqual(product.lifecycle, LIFECYCLE_DRAFT)

    def test_legacy_status_fallback(self):
        product = SimpleNamespace(status=True, lifecycle=None)
        self.assertEqual(lifecycle_of(product), LIFECYCLE_ACTIVE)
        product2 = SimpleNamespace(status=False, lifecycle=None)
        self.assertEqual(lifecycle_of(product2), LIFECYCLE_DRAFT)


if __name__ == "__main__":
    unittest.main()
