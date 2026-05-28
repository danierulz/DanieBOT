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


if __name__ == "__main__":
    unittest.main()
