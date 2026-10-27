import io
import json
import os
import unittest
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault("JWT_SECRET_KEY", "ci-test-jwt-secret-not-for-prod")
os.environ.setdefault("ADMIN_USERNAME", "ci-admin")

from provider_importers.bulk.markup import apply_price_markup
from provider_importers.bulk.runner import main
from provider_importers.types import ImportedProduct


def _product(**overrides) -> ImportedProduct:
    fields = dict(
        provider="sochic",
        source_url="https://sochic.com.ar/product/campera/",
        title="Campera",
        description="d",
        price=10000,
        cod_product="sochic-campera",
        original_price=12500,
        discount_percent=20,
    )
    fields.update(overrides)
    return ImportedProduct(**fields)


class ApplyPriceMarkupTest(unittest.TestCase):
    def test_zero_percent_leaves_prices(self):
        product = _product()
        same = apply_price_markup(product, 0)
        self.assertIs(same, product)
        self.assertEqual(product.price, 10000)
        self.assertEqual(product.original_price, 12500)
        self.assertEqual(product.discount_percent, 20)

    def test_markup_scales_price_and_original_price(self):
        product = apply_price_markup(_product(), 10)
        self.assertEqual(product.price, 11000)
        self.assertEqual(product.original_price, 13750)
        self.assertEqual(product.discount_percent, 20)
        self.assertEqual(product.title, "Campera")

    def test_half_up_rounds_away_from_zero_on_ties(self):
        # 10 * 1.25 = 12.5. Half-up is 13; banker's round would leave 12.
        product = apply_price_markup(_product(price=10, original_price=None), 25)
        self.assertEqual(product.price, 13)
        self.assertIsNone(product.original_price)

    def test_unset_original_price_stays_unset_and_zero_is_marked(self):
        missing = apply_price_markup(_product(original_price=None), 30)
        self.assertEqual(missing.price, 13000)
        self.assertIsNone(missing.original_price)
        zero = apply_price_markup(_product(price=0, original_price=0), 10)
        self.assertEqual(zero.price, 0)
        self.assertEqual(zero.original_price, 0)

    def test_negative_percent_lowers_the_price(self):
        product = apply_price_markup(_product(original_price=None), -10)
        self.assertEqual(product.price, 9000)
        self.assertIsNone(product.original_price)

    def test_rejects_non_finite_percent(self):
        with self.assertRaises(ValueError):
            apply_price_markup(_product(), float("nan"))


class MarkupCliTest(unittest.TestCase):
    def test_dry_run_prints_markup_without_fetching(self):
        fetch = MagicMock(side_effect=AssertionError("dry-run no fetchea"))
        buf = io.StringIO()
        with patch("provider_importers.bulk.runner.read_known_source_urls", return_value=set()):
            with patch.dict("provider_importers.bulk.runner._FETCHERS", {"sochic": fetch}):
                with redirect_stdout(buf), redirect_stderr(io.StringIO()):
                    code = main(
                        [
                            "--provider",
                            "sochic",
                            "--dry-run",
                            "--price-markup-percent",
                            "12.5",
                            "--url",
                            "https://sochic.com.ar/product/a/",
                        ]
                    )
        self.assertEqual(code, 0)
        fetch.assert_not_called()
        payload = json.loads(buf.getvalue())
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["price_markup_percent"], 12.5)
        self.assertEqual(payload["would_fetch"], 1)
        self.assertEqual(payload["created"], 0)

    def test_markup_is_applied_after_fetch_and_before_persist(self):
        imported = _product(source_url="https://sochic.com.ar/product/a/", price=10000, original_price=12500)
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        seen = {}

        def persist(session, product, payload, uploader, **kwargs):
            seen["price"] = product.price
            seen["original_price"] = product.original_price
            seen["discount_percent"] = product.discount_percent
            return {"created": True}

        @contextmanager
        def session():
            yield db

        buf = io.StringIO()
        with patch("provider_importers.bulk.runner.read_known_source_urls", return_value=set()):
            with patch.dict(
                "provider_importers.bulk.runner._FETCHERS",
                {"sochic": lambda url: imported},
            ):
                with patch("provider_importers.bulk.runner.persist_imported_product", side_effect=persist):
                    with patch("provider_importers.bulk.runner.create_uploader", return_value=MagicMock()):
                        with patch("provider_importers.bulk.runner.get_db_session", session):
                            with redirect_stdout(buf), redirect_stderr(io.StringIO()):
                                code = main(
                                    [
                                        "--provider",
                                        "sochic",
                                        "--url",
                                        "https://sochic.com.ar/product/a/",
                                        "--price-markup-percent",
                                        "10",
                                        "--delay-ms",
                                        "0",
                                    ]
                                )
        self.assertEqual(code, 0)
        self.assertEqual(seen["price"], 11000)
        self.assertEqual(seen["original_price"], 13750)
        self.assertEqual(seen["discount_percent"], 20)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["price_markup_percent"], 10)
        self.assertEqual(payload["created"], 1)
        self.assertEqual(payload["failed"], 0)
        self.assertNotIn("dry_run", payload)

    def test_non_finite_markup_is_rejected_before_fetch(self):
        with patch(
            "provider_importers.bulk.runner.read_known_source_urls",
            side_effect=AssertionError("no debería leer la base"),
        ):
            with redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    main(
                        [
                            "--provider",
                            "sochic",
                            "--dry-run",
                            "--price-markup-percent",
                            "nan",
                            "--url",
                            "https://sochic.com.ar/product/a/",
                        ]
                    )

    def test_tracked_run_rejects_nonzero_markup(self):
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                main(
                    [
                        "--provider",
                        "nissie",
                        "--tracked-run",
                        "--price-markup-percent",
                        "10",
                        "--url",
                        "https://nissiedenim.com.ar/productos/a/",
                    ]
                )
        self.assertIn("tracked-run", str(ctx.exception))


class ScrapingCareDocTest(unittest.TestCase):
    def test_ops_doc_is_linked_from_the_specs(self):
        root = Path(__file__).resolve().parents[1]
        ops = (root / "docs/ops/scraping-cuidados.md").read_text(encoding="utf-8")
        spec17 = (root / "docs/specs/17-scraping-masivo-proveedores.md").read_text(encoding="utf-8")
        spec23 = (root / "docs/specs/23-bulk-import-notebook.md").read_text(encoding="utf-8")
        self.assertIn("--price-markup-percent", ops)
        self.assertIn("--dry-run", ops)
        self.assertIn("--skip-existing", ops)
        self.assertIn("429", ops)
        self.assertIn("notebook", ops.lower())
        self.assertIn("17-scraping-masivo-proveedores.md", ops)
        self.assertIn("18-import-proveedores-patrones.md", ops)
        self.assertIn("21-admin-importacion-masiva.md", ops)
        self.assertIn("23-bulk-import-notebook.md", ops)
        self.assertIn("Cloud Scheduler", ops)
        self.assertIn("Cloud Run", ops)
        self.assertIn("GitHub Actions", ops)
        self.assertIn("scraping-cuidados.md", spec17)
        self.assertIn("scraping-cuidados.md", spec23)
        self.assertIn("5000", spec17)
