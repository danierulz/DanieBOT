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
from database.models.ProviderImportRun import ProviderImportRun
from database.models.Size import Size
from provider_importers.types import ImportedProduct, ProviderImportError
from services.laslocas_bulk_import import create_bulk_run, run_laslocas_bulk_import


class LasLocasBulkImportTest(unittest.TestCase):
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

    def test_bulk_import_created_and_failed(self):
        session = self.SessionLocal()
        run = create_bulk_run(session, triggered_by="admin")
        urls = [
            "https://laslocas.com/ficha-1-new",
            "https://laslocas.com/ficha-2-broken",
        ]
        imported = ImportedProduct(
            provider="laslocas",
            source_url=urls[0],
            title="New",
            description="desc",
            price=10000,
            cod_product="LL-NEW",
            sku=1,
            image_assets=[("a.jpg", b"x")],
        )
        uploader = MagicMock()
        uploader.upload_bytes.return_value = "https://storage.googleapis.com/bucket/a.jpg"

        with patch("services.laslocas_bulk_import.discover_laslocas_product_urls", return_value=urls):
            with patch("services.laslocas_bulk_import.fetch_laslocas_product") as fetch_mock:
                fetch_mock.side_effect = [
                    imported,
                    ProviderImportError("No se pudo detectar el precio"),
                ]
                with patch("services.laslocas_bulk_import.persist_imported_product") as persist_mock:
                    persist_mock.return_value = {
                        "ok": True,
                        "created": True,
                        "id": 7,
                        "provider": "laslocas",
                        "cod_product": "LL-NEW",
                        "activo": False,
                    }
                    run_laslocas_bulk_import(
                        session,
                        run.run_id,
                        uploader,
                        sync_variants_fn=MagicMock(),
                        match_color_ids_fn=MagicMock(return_value=[]),
                    )

        session.refresh(run)
        self.assertEqual(run.status, "completed")
        self.assertEqual(run.discovered, 2)
        self.assertEqual(run.created, 1)
        self.assertEqual(run.failed, 1)
        session.close()


if __name__ == "__main__":
    unittest.main()
