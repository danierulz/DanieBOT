import json
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "test")

from fastapi.testclient import TestClient

import main
from config import get_template_context

ROOT = Path(__file__).resolve().parents[1]


class BrandLogoTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def test_brand_logo_static_assets_exist(self):
        for path in (
            "/static/css/brand-logo.css",
            "/static/css/brand-logo-dev.css",
            "/static/js/brandLogo.js",
            "/static/brand/logo-source.png",
            "/static/brand/logo-extracted.json",
            "/static/brand/logo-meta.json",
            "/static/brand/logo-calibration.json",
        ):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)

    def test_logo_extracted_json_has_expected_layers(self):
        data = json.loads((ROOT / "static" / "brand" / "logo-extracted.json").read_text(encoding="utf-8"))
        self.assertEqual(data["view_box"], "0 0 666 714")
        self.assertGreater(data["stem_length"], 100)
        self.assertGreaterEqual(len(data["letters"]), 1)
        self.assertIn("brand-logo__letter-o", data["letters"][0]["cls"])
        self.assertTrue(any("brand-logo__stem" in layer["cls"] for layer in data["jasmine"]))
        self.assertTrue(any("brand-logo__leaf--" in layer["cls"] for layer in data["jasmine"]))

    def test_logo_meta_matches_extracted_counts(self):
        extracted = json.loads((ROOT / "static" / "brand" / "logo-extracted.json").read_text(encoding="utf-8"))
        meta = json.loads((ROOT / "static" / "brand" / "logo-meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["stem_length"], extracted["stem_length"])
        self.assertEqual(meta["leaf_count"], extracted["leaf_count"])
        self.assertGreaterEqual(meta["bud_count"], 2)
        self.assertGreaterEqual(meta["petal_count"], 4)
        self.assertGreater(meta["stem_length"], 100)

    @patch("main.build_nav_links", return_value=[])
    @patch("main.list_categories_for_nav", return_value=[])
    @patch("main.SessionLocal")
    def test_home_includes_brand_logo_script(self, mock_session_local, _nav, _links):
        mock_session_local.return_value = MagicMock()
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("brandLogo.js", html)
        self.assertIn("Outfit Jazmines", html)

    def test_template_context_exposes_logo_settings(self):
        ctx = get_template_context()
        self.assertIn("brand_logo_animated", ctx)
        self.assertIn("brand_logo_colors", ctx)
        self.assertIn("bud", ctx["brand_logo_colors"])
        self.assertEqual(ctx["brand_logo_colors"]["letter"], "#111111")

    def test_dev_preview_hidden_without_debug(self):
        with patch("main.APP_DEBUG", False):
            response = self.client.get("/dev/brand-logo")
            self.assertEqual(response.status_code, 404)

    def test_dev_preview_available_with_debug(self):
        with patch("main.APP_DEBUG", True):
            response = self.client.get("/dev/brand-logo")
            self.assertEqual(response.status_code, 200)
            html = response.text
            self.assertIn("Preview logo", html)
            self.assertIn("btn-play", html)
            self.assertIn("brand-logo-dev.css", html)
            self.assertIn("view-mode", html)
            self.assertIn("btn-hover", html)
            self.assertIn("cal-letters-tx", html)
            self.assertIn("btn-export-calibration", html)
            self.assertIn("layer-letters", html)
            self.assertIn("logo-meta-counts", html)
            self.assertIn('value="diff"', html)

    def test_dev_calibration_endpoint(self):
        payload = {
            "letters": {"tx": 2, "ty": -1, "scale": 1.01},
            "jasmine": {"tx": 0, "ty": 3, "scale": 0.99},
        }
        with patch("main.APP_DEBUG", False):
            blocked = self.client.post("/dev/brand-logo/calibration", json=payload)
            self.assertEqual(blocked.status_code, 404)
        with patch("main.APP_DEBUG", True):
            saved = self.client.post("/dev/brand-logo/calibration", json=payload)
            self.assertEqual(saved.status_code, 200)
            self.assertTrue(saved.json()["ok"])
        calibration = json.loads((ROOT / "static" / "brand" / "logo-calibration.json").read_text(encoding="utf-8"))
        self.assertEqual(calibration["letters"]["tx"], 2)
        self.assertAlmostEqual(calibration["jasmine"]["scale"], 0.99)
        # restore defaults for other tests / dev workflow
        (ROOT / "static" / "brand" / "logo-calibration.json").write_text(
            json.dumps(
                {
                    "letters": {"tx": 0, "ty": 0, "scale": 1},
                    "jasmine": {"tx": 0, "ty": 0, "scale": 1},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    @patch("main.build_nav_links", return_value=[])
    @patch("main.list_categories_for_nav", return_value=[])
    @patch("main.SessionLocal")
    def test_home_has_white_header(self, mock_session_local, _nav, _links):
        mock_session_local.return_value = MagicMock()
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("bg-white", response.text)

    def test_favicon_served(self):
        response = self.client.get("/favicon.ico")
        self.assertEqual(response.status_code, 200)
        self.assertIn("svg", response.headers.get("content-type", ""))


if __name__ == "__main__":
    unittest.main()
