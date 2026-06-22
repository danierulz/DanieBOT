import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "test")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database.models  # noqa: F401
from database.init_db import Base
from database.models.Products import Products
from database.models.ProviderImportRun import ProviderImportRun
from database.models.Size import Size
from provider_importers.types import ImportedProduct, ProviderImportError
from services.holic_bulk_import import create_bulk_run, run_holic_bulk_import


class HolicBulkImportTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(self.engine)
        session = self.SessionLocal()
        session.add(Size(code="UNICO", label="Unico", sort_order=70))
        session.commit()
        session.close()

    def tearDown(self):
        Base.metadata.drop_all(self.engine)

    @patch("services.holic_bulk_import.time.sleep")
    def test_bulk_import_created_skipped_failed(self, _sleep_mock):
        session = self.SessionLocal()
        run = create_bulk_run(session, triggered_by="admin")
        urls = [
            "https://holiclothing.com.ar/product/new-product/",
            "https://holiclothing.com.ar/product/existing/",
            "https://holiclothing.com.ar/product/broken/",
        ]
        session.add(
            Products(
                item_title="Existing",
                price=1000,
                cod_product="holic-r999-existing",
                name="Existing",
                status=False,
                provider="holic",
            )
        )
        session.commit()

        imported_new = ImportedProduct(
            provider="holic",
            source_url=urls[0],
            title="New Product",
            description="desc",
            price=9400,
            cod_product="holic-r111-new-product",
            image_urls=["https://holiclothing.com.ar/wp-content/uploads/a.jpg"],
        )
        imported_existing = ImportedProduct(
            provider="holic",
            source_url=urls[1],
            title="Existing",
            description="desc",
            price=9400,
            cod_product="holic-r999-existing",
        )

        uploader = MagicMock()
        sync_variants = MagicMock()
        match_colors = MagicMock(return_value=[])

        with patch("services.holic_bulk_import.discover_holic_product_urls", return_value=urls):
            with patch("services.holic_bulk_import.fetch_holic_product") as fetch_mock:
                fetch_mock.side_effect = [
                    imported_new,
                    imported_existing,
                    ProviderImportError("No se pudo detectar el precio"),
                ]
                with patch("services.holic_bulk_import.persist_imported_product") as persist_mock:
                    persist_mock.return_value = {
                        "ok": True,
                        "created": True,
                        "id": 42,
                        "provider": "holic",
                        "cod_product": "holic-r111-new-product",
                        "activo": False,
                    }
                    run_holic_bulk_import(
                        session,
                        run.run_id,
                        uploader,
                        sync_variants_fn=sync_variants,
                        match_color_ids_fn=match_colors,
                    )

        session.refresh(run)
        self.assertEqual(run.status, "completed")
        self.assertEqual(run.discovered, 3)
        self.assertEqual(run.created, 1)
        self.assertEqual(run.skipped, 1)
        self.assertEqual(run.failed, 1)
        session.close()

    @patch("services.holic_bulk_import.time.sleep")
    def test_second_run_skips_existing(self, _sleep_mock):
        session = self.SessionLocal()
        session.add(
            Products(
                item_title="Already",
                price=1000,
                cod_product="holic-r111-already",
                name="Already",
                status=True,
                provider="holic",
            )
        )
        session.commit()
        run = create_bulk_run(session, triggered_by="admin")
        urls = ["https://holiclothing.com.ar/product/already/"]
        imported = ImportedProduct(
            provider="holic",
            source_url=urls[0],
            title="Already",
            description="desc",
            price=9400,
            cod_product="holic-r111-already",
        )
        uploader = MagicMock()
        with patch("services.holic_bulk_import.discover_holic_product_urls", return_value=urls):
            with patch("services.holic_bulk_import.fetch_holic_product", return_value=imported):
                run_holic_bulk_import(
                    session,
                    run.run_id,
                    uploader,
                    sync_variants_fn=MagicMock(),
                    match_color_ids_fn=MagicMock(return_value=[]),
                )
        session.refresh(run)
        self.assertEqual(run.created, 0)
        self.assertEqual(run.skipped, 1)
        self.assertEqual(session.query(Products).count(), 1)
        session.close()


if __name__ == "__main__":
    unittest.main()
