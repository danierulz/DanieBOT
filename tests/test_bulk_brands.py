import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault("JWT_SECRET_KEY", "ci-test-jwt-secret-not-for-prod")
os.environ.setdefault("ADMIN_USERNAME", "ci-admin")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database.models  # noqa: F401
from database.init_db import Base
from database.models.Products import Products
from database.models.ProviderImportRun import ProviderImportRun
from database.models.ProviderImportRunItem import ProviderImportRunItem
from provider_importers.bulk.brands import (
    BrandConfigError,
    format_brand_list,
    load_brand_registry,
)
from provider_importers.bulk.existing import (
    canonical_source_url,
    load_known_source_urls,
    select_import_urls,
)
from provider_importers.bulk.runner import build_parser, discover_urls, main
from provider_importers.bulk.types import BulkImportOptions
from provider_importers.types import ImportedProduct
from services.nissie_bulk_import import create_bulk_run, run_nissie_bulk_import
from services.provider_import import ProviderImportPayload, persist_imported_product


class BrandRegistryTest(unittest.TestCase):
    def test_shipped_registry_is_notebook_only(self):
        registry = load_brand_registry()
        self.assertTrue(registry.notebook_only)
        self.assertIn("cloud_run", registry.do_not_schedule)
        self.assertIn("cloud_scheduler", registry.do_not_schedule)
        self.assertIn("github_actions", registry.do_not_schedule)
        self.assertEqual(registry.ids(), ["laslocas", "nissie", "holic", "sochic"])
        laslocas = registry.get("laslocas")
        self.assertEqual(laslocas.mode, "categories")
        self.assertTrue(laslocas.requires_login)
        self.assertEqual(laslocas.login_env, ("LOGIN_EMAIL", "LOGIN_PASS"))
        sochic = registry.get("sochic")
        self.assertEqual(sochic.mode, "catalog")
        self.assertFalse(sochic.requires_login)
        self.assertEqual(sochic.default_delay_ms, 5000)
        text = format_brand_list()
        self.assertIn("notebook", text)
        self.assertIn("Cloud Scheduler", text)
        self.assertIn("sochic", text)

    def test_parser_choices_follow_the_registry(self):
        choices = next(action.choices for action in build_parser()._actions if action.dest == "provider")
        self.assertEqual(list(choices), ["laslocas", "nissie", "holic", "sochic"])

    def test_rejects_scheduling_opt_in_and_bad_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "brands.json"
            path.write_text(json.dumps({"notebook_only": False, "brands": []}), encoding="utf-8")
            with self.assertRaises(BrandConfigError):
                load_brand_registry(path)

            path.write_text(
                json.dumps(
                    {
                        "notebook_only": True,
                        "do_not_schedule": ["cloud_run"],
                        "brands": [
                            _brand("laslocas"),
                            _brand("laslocas"),
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(BrandConfigError):
                load_brand_registry(path)

            broken = _brand("sochic")
            broken["mode"] = "sitemap"
            path.write_text(
                json.dumps(
                    {
                        "notebook_only": True,
                        "do_not_schedule": ["cloud_run"],
                        "brands": [broken],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(BrandConfigError):
                load_brand_registry(path)


class ExistingUrlSelectionTest(unittest.TestCase):
    def test_canonical_ignores_www_query_and_slash(self):
        left = canonical_source_url("https://www.sochic.com.ar/product/campera/?utm=1")
        right = canonical_source_url("http://sochic.com.ar/product/campera")
        self.assertEqual(left, right)
        self.assertEqual(left, "https://sochic.com.ar/product/campera")

    def test_limit_applies_after_skipping_known_urls(self):
        known = {canonical_source_url("https://sochic.com.ar/product/a/")}
        urls = [
            "https://www.sochic.com.ar/product/a",
            "https://sochic.com.ar/product/b/",
            "https://sochic.com.ar/product/c/",
        ]
        selection = select_import_urls(urls, skip_existing=True, known_urls=known, limit=1)
        self.assertEqual(len(selection.discovered), 3)
        self.assertEqual(len(selection.skipped_existing), 1)
        self.assertEqual(list(selection.to_fetch), ["https://sochic.com.ar/product/b/"])

        refresh = select_import_urls(urls, skip_existing=False, known_urls=known, limit=2)
        self.assertEqual(refresh.skipped_existing, ())
        self.assertEqual(len(refresh.to_fetch), 2)


class KnownSourceUrlDbTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        Base.metadata.drop_all(self.engine)

    def test_known_urls_come_from_product_and_successful_run_items(self):
        session = self.SessionLocal()
        session.add(
            Products(
                item_title="Stored",
                price=1000,
                cod_product="sochic-1-stored",
                name="Stored",
                provider="sochic",
                provider_source_url="https://www.sochic.com.ar/product/stored/",
            )
        )
        session.add(
            Products(
                item_title="From run",
                price=1000,
                cod_product="nissie-9",
                name="From run",
                provider="nissie",
            )
        )
        run = ProviderImportRun(provider="nissie", status="completed", phase="completed")
        session.add(run)
        session.flush()
        session.add(
            ProviderImportRunItem(
                run_id=run.run_id,
                source_url="https://nissiedenim.com.ar/productos/from-run/",
                cod_product="nissie-9",
                status="created",
            )
        )
        session.add(
            ProviderImportRunItem(
                run_id=run.run_id,
                source_url="https://nissiedenim.com.ar/productos/failed/",
                cod_product="nissie-9",
                status="failed",
            )
        )
        session.add(
            ProviderImportRunItem(
                run_id=run.run_id,
                source_url="https://nissiedenim.com.ar/productos/deleted/",
                cod_product="nissie-missing",
                status="created",
            )
        )
        session.commit()

        known = load_known_source_urls(session)
        self.assertIn("https://sochic.com.ar/product/stored", known)
        self.assertIn("https://nissiedenim.com.ar/productos/from-run", known)
        self.assertNotIn("https://nissiedenim.com.ar/productos/failed", known)
        self.assertNotIn("https://nissiedenim.com.ar/productos/deleted", known)
        session.close()

    def test_persist_stores_and_backfills_source_url(self):
        session = self.SessionLocal()
        imported = ImportedProduct(
            provider="sochic",
            source_url="https://sochic.com.ar/product/campera-friza/",
            title="Campera",
            description="d",
            price=10000,
            cod_product="sochic-1-campera",
        )
        uploader = MagicMock()
        created = persist_imported_product(
            session,
            imported,
            ProviderImportPayload(status=False),
            uploader,
            sync_variants_fn=MagicMock(),
            match_color_ids_fn=MagicMock(return_value=[]),
        )
        self.assertTrue(created["created"])
        row = session.query(Products).one()
        self.assertEqual(row.provider_source_url, imported.source_url)

        row.provider_source_url = None
        session.commit()
        again = persist_imported_product(
            session,
            imported,
            ProviderImportPayload(status=False),
            uploader,
            sync_variants_fn=MagicMock(),
            match_color_ids_fn=MagicMock(return_value=[]),
        )
        self.assertFalse(again["created"])
        session.refresh(row)
        self.assertEqual(row.provider_source_url, imported.source_url)
        self.assertEqual(session.query(Products).count(), 1)
        session.close()


class BulkCliTest(unittest.TestCase):
    def test_list_brands_does_not_require_provider(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(["--list-brands"])
        self.assertEqual(code, 0)
        text = buf.getvalue()
        self.assertIn("laslocas", text)
        self.assertIn("sochic", text)
        self.assertIn("Cloud Run", text)

    def test_dry_run_reports_skip_and_fetch_after_limit(self):
        known = {canonical_source_url("https://sochic.com.ar/product/a/")}
        buf = io.StringIO()
        with patch("provider_importers.bulk.runner.read_known_source_urls", return_value=known):
            with redirect_stdout(buf), redirect_stderr(io.StringIO()):
                code = main(
                    [
                        "--provider",
                        "sochic",
                        "--dry-run",
                        "--limit",
                        "1",
                        "--url",
                        "https://www.sochic.com.ar/product/a",
                        "--url",
                        "https://sochic.com.ar/product/b/",
                        "--url",
                        "https://sochic.com.ar/product/c/",
                    ]
                )
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["discovered"], 3)
        self.assertEqual(payload["would_skip_existing"], 1)
        self.assertEqual(payload["would_fetch"], 1)
        self.assertEqual(payload["urls"], ["https://sochic.com.ar/product/b/"])
        self.assertEqual(payload["delay_ms"], 5000)
        self.assertEqual(payload["price_markup_percent"], 0)
        self.assertTrue(payload["skip_existing"])
        self.assertEqual(payload["skipped"], 0)

    def test_no_skip_existing_does_not_read_the_database(self):
        buf = io.StringIO()
        with patch("provider_importers.bulk.runner.read_known_source_urls") as known:
            with redirect_stdout(buf), redirect_stderr(io.StringIO()):
                code = main(
                    [
                        "--provider",
                        "sochic",
                        "--dry-run",
                        "--no-skip-existing",
                        "--limit",
                        "1",
                        "--url",
                        "https://sochic.com.ar/product/a/",
                        "--url",
                        "https://sochic.com.ar/product/b/",
                    ]
                )
        self.assertEqual(code, 0)
        known.assert_not_called()
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["would_skip_existing"], 0)
        self.assertEqual(payload["would_fetch"], 1)
        self.assertFalse(payload["skip_existing"])

    def test_laslocas_dry_run_refuses_missing_login_without_printing_secrets(self):
        with patch.dict(os.environ, {"LOGIN_EMAIL": "", "LOGIN_PASS": ""}, clear=False):
            with patch(
                "provider_importers.bulk.runner.discover_laslocas_product_urls",
                side_effect=AssertionError("no debería descubrir"),
            ):
                with self.assertRaises(SystemExit) as ctx:
                    main(["--provider", "laslocas", "--category", "denim", "--dry-run"])
        message = str(ctx.exception)
        self.assertIn("LOGIN_EMAIL", message)
        self.assertIn("LOGIN_PASS", message)
        self.assertNotIn("@", message)

    def test_sochic_tracked_run_is_rejected(self):
        with self.assertRaises(SystemExit) as ctx:
            main(
                [
                    "--provider",
                    "sochic",
                    "--tracked-run",
                    "--url",
                    "https://sochic.com.ar/product/a/",
                ]
            )
        self.assertIn("tracked", str(ctx.exception).lower())

    def test_sochic_discover_receives_category_and_max_pages(self):
        with patch(
            "provider_importers.bulk.runner.discover_sochic_product_urls",
            return_value=["https://sochic.com.ar/product/a/"],
        ) as discover:
            urls = discover_urls(
                BulkImportOptions(provider="sochic", category_id="camperas", max_pages=1)
            )
        self.assertEqual(urls, ["https://sochic.com.ar/product/a/"])
        self.assertEqual(discover.call_args.kwargs["category_slug"], "camperas")
        self.assertEqual(discover.call_args.kwargs["max_pages"], 1)

    def test_nissie_category_flag_is_ignored(self):
        err = io.StringIO()
        with patch("provider_importers.bulk.runner.read_known_source_urls", return_value=set()):
            with redirect_stdout(io.StringIO()), redirect_stderr(err):
                code = main(
                    [
                        "--provider",
                        "nissie",
                        "--dry-run",
                        "--category",
                        "jeans",
                        "--url",
                        "https://nissiedenim.com.ar/productos/a/",
                    ]
                )
        self.assertEqual(code, 0)
        self.assertIn("--category", err.getvalue())


class NissiePreskipServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        Base.metadata.drop_all(self.engine)

    def test_does_not_fetch_url_already_stored(self):
        session = self.SessionLocal()
        known_url = "https://nissiedenim.com.ar/productos/ya-esta/"
        new_url = "https://nissiedenim.com.ar/productos/nueva/"
        session.add(
            Products(
                item_title="Ya",
                price=1000,
                cod_product="nissie-1",
                name="Ya",
                provider="nissie",
                provider_source_url=known_url,
            )
        )
        session.commit()
        run = create_bulk_run(session, triggered_by="cli")
        imported = ImportedProduct(
            provider="nissie",
            source_url=new_url,
            title="Nueva",
            description="d",
            price=20000,
            cod_product="nissie-2",
            sku=2,
        )
        with patch(
            "services.nissie_bulk_import.discover_nissie_product_urls",
            return_value=[known_url, new_url],
        ):
            with patch(
                "services.nissie_bulk_import.fetch_nissie_product",
                return_value=imported,
            ) as fetch:
                with patch(
                    "services.nissie_bulk_import.persist_imported_product",
                    return_value={"ok": True, "created": True, "id": 3, "cod_product": "nissie-2"},
                ) as persist:
                    with patch("services.nissie_bulk_import.time.sleep"):
                        run_nissie_bulk_import(
                            session,
                            run.run_id,
                            MagicMock(),
                            sync_variants_fn=MagicMock(),
                            match_color_ids_fn=MagicMock(return_value=[]),
                            limit=10,
                            skip_existing=True,
                        )
        fetch.assert_called_once_with(new_url)
        persist.assert_called_once()
        session.refresh(run)
        self.assertEqual(run.discovered, 2)
        self.assertEqual(run.skipped, 1)
        self.assertEqual(run.created, 1)
        session.close()


def _brand(brand_id: str) -> dict:
    return {
        "id": brand_id,
        "display_name": brand_id,
        "mode": "catalog",
        "requires_login": False,
        "login_env": [],
        "default_delay_ms": 1500,
        "notes": "nota",
    }


if __name__ == "__main__":
    unittest.main()
