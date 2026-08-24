import os
import re
import unittest

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "test")

from fastapi.testclient import TestClient

import main
from config import get_template_context


class AdminPanelTemplateTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def test_admin_panel_renders(self):
        response = self.client.get("/admin-panel")
        self.assertEqual(response.status_code, 200, response.text[:500])
        self.assertIn("admin-panel", response.text)

    def test_admin_panel_tojson_vars_in_config(self):
        with open("templates/admin-panel.html", encoding="utf-8") as f:
            html = f.read()
        keys = set(re.findall(r"\{\{\s*(admin_[a-z0-9_]+)\s*\|\s*tojson", html))
        ctx = get_template_context()
        missing = sorted(k for k in keys if k not in ctx)
        self.assertEqual(missing, [], f"Missing template context keys: {missing}")

    def test_admin_panel_links_help(self):
        response = self.client.get("/admin-panel")
        self.assertEqual(response.status_code, 200)
        self.assertIn("/admin-panel/ayuda", response.text)
        self.assertIn("Ayuda", response.text)

    def test_admin_help_renders(self):
        response = self.client.get("/admin-panel/ayuda")
        self.assertEqual(response.status_code, 200, response.text[:500])
        self.assertIn("Manual de la administradora", response.text)
        self.assertIn("Talles y disponibilidad", response.text)
        self.assertIn("no se avisa otra vez", response.text)
        self.assertIn("/admin-panel", response.text)

    def test_product_detail_selects_color_before_sizes(self):
        with open("templates/tiredimages.html", encoding="utf-8") as f:
            html = f.read()
        fetch_at = html.find("fetch('/api/producto/'")
        self.assertGreater(fetch_at, 0)
        tail = html[fetch_at:]
        apply_at = tail.find("applyDefaultColorSelection();")
        color_at = tail.find("renderColorChips();")
        sizes_at = tail.find("renderSizeChips();")
        self.assertGreater(apply_at, 0)
        self.assertLess(apply_at, color_at)
        self.assertLess(color_at, sizes_at)
        self.assertIn("const sizesToShow = productSizes();", html)


if __name__ == "__main__":
    unittest.main()
