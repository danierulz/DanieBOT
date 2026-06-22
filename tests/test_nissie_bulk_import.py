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
from services.nissie_bulk_import import create_bulk_run, run_nissie_bulk_import


class NissieBulkImportTest(unittest.TestCase):
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

    def test_bulk_import_created_skipped_failed(self):
        session = self.SessionLocal()
        run = create_bulk_run(session, triggered_by="admin")
        urls = [
            "https://nissiedenim.com.ar/productos/new-product/",
            "https://nissiedenim.com.ar/productos/existing/",
            "https://nissiedenim.com.ar/productos/broken/",
        ]
        session.add(
            Products(
                item_title="Existing",
                price=1000,
                cod_product="nissie-999",
                name="Existing",
                status=False,
                provider="nissie",
            )
        )
        session.commit()

        imported_new = ImportedProduct(
            provider="nissie",
            source_url=urls[0],
            title="New Product",
            description="desc",
            price=24000,
            cod_product="nissie-111",
            sku=111,
            image_urls=["https://example.com/a.webp"],
        )
        imported_existing = ImportedProduct(
            provider="nissie",
            source_url=urls[1],
            title="Existing",
            description="desc",
            price=24000,
            cod_product="nissie-999",
            sku=999,
        )

        uploader = MagicMock()
        sync_variants = MagicMock()
        match_colors = MagicMock(return_value=[])

        with patch("services.nissie_bulk_import.discover_nissie_product_urls", return_value=urls):
            with patch("services.nissie_bulk_import.fetch_nissie_product") as fetch_mock:
                fetch_mock.side_effect = [
                    imported_new,
                    imported_existing,
                    ProviderImportError("No se pudo detectar el precio"),
                ]
                with patch("services.nissie_bulk_import.persist_imported_product") as persist_mock:
                    persist_mock.return_value = {
                        "ok": True,
                        "created": True,
                        "id": 42,
                        "provider": "nissie",
                        "cod_product": "nissie-111",
                        "activo": False,
                    }
                    run_nissie_bulk_import(
                        session,
                        run.run_id,
                        uploader,
                        sync_variants_fn=sync_variants,
                        match_color_ids_fn=match_colors,
                    )

        session.refresh(run)
        self.assertEqual(run.status, "completed")
        self.assertEqual(run.phase, "completed")
        self.assertEqual(run.discovered, 3)
        self.assertEqual(run.created, 1)
        self.assertEqual(run.skipped, 1)
        self.assertEqual(run.failed, 1)
        session.close()

    def test_second_run_skips_existing(self):
        session = self.SessionLocal()
        session.add(
            Products(
                item_title="Already",
                price=1000,
                cod_product="nissie-111",
                name="Already",
                status=True,
                provider="nissie",
            )
        )
        session.commit()
        run = create_bulk_run(session, triggered_by="admin")
        urls = ["https://nissiedenim.com.ar/productos/already/"]
        imported = ImportedProduct(
            provider="nissie",
            source_url=urls[0],
            title="Already",
            description="desc",
            price=24000,
            cod_product="nissie-111",
            sku=111,
        )
        uploader = MagicMock()
        with patch("services.nissie_bulk_import.discover_nissie_product_urls", return_value=urls):
            with patch("services.nissie_bulk_import.fetch_nissie_product", return_value=imported):
                run_nissie_bulk_import(
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
