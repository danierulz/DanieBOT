import os
import unittest
from unittest.mock import patch

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "test")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database.models  # noqa: F401
import main
from database.init_db import Base
from database.models.Category import Category
from database.models.ProductImages import ProductImages
from database.models.Products import Products
from database.models.ProductVariant import ProductVariant
from database.models.ProviderImportRun import ProviderImportRun
from database.models.Size import Size
from provider_importers.types import ImportedProduct, ProviderImportError


class ProviderImportEndpointTest(unittest.TestCase):
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
        session.add(Category(slug="camperas", name="Camperas", sort_order=60, activo=True))
        session.commit()
        session.close()

        def override_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        main.app.dependency_overrides[main.get_db_fastApi] = override_db
        main.app.dependency_overrides[main.get_current_user] = lambda: {"sub": "admin"}
        self.client = TestClient(main.app)

    def tearDown(self):
        main.app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)

    def test_unified_import_sochic_creates_inactive_product(self):
        imported = ImportedProduct(
            provider="sochic",
            source_url="https://sochic.com.ar/product/campera-friza-young-leaders/",
            title="Campera Friza Young Leaders",
            description="MEDIDAS CONTORNO PECHO: 58",
            price=26100,
            original_price=29000,
            discount_percent=10,
            is_sale=True,
            sku=3515,
            cod_product="sochic-3515-campera-friza-young-leaders",
            image_urls=["https://sochic.com.ar/wp-content/uploads/main.jpeg"],
            category_slug="camperas",
            colors=["Celeste"],
        )

        with patch.object(main, "fetch_product", return_value=imported):
            response = self.client.post(
                "/api/proveedores/importar",
                json={"url": imported.source_url, "status": False},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["created"])
        self.assertEqual(body["provider"], "sochic")

        session = self.SessionLocal()
        try:
            product = session.query(Products).one()
            self.assertFalse(product.status)
            self.assertEqual(session.query(ProductImages).count(), 1)
            self.assertEqual(session.query(ProductVariant).count(), 1)
        finally:
            session.close()

    def test_unified_import_laslocas_uploads_to_gcs(self):
        imported = ImportedProduct(
            provider="laslocas",
            source_url="https://laslocas.com/ficha-224-jogger-blue-sporty",
            title="BLUE SPORTY",
            description="Jogger denim",
            price=12500,
            cod_product="BSPOR",
            sku=224,
            page_ficha="ficha-224-jogger-blue-sporty",
            image_assets=[("foto1.jpg", b"binary-image")],
        )

        with patch.object(main, "fetch_product", return_value=imported):
            with patch.object(main.uploader, "upload_bytes", return_value="https://storage.googleapis.com/bucket/x.jpg"):
                response = self.client.post(
                    "/api/proveedores/importar",
                    json={"url": imported.source_url},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "laslocas")

        session = self.SessionLocal()
        try:
            product = session.query(Products).one()
            self.assertFalse(product.status)
            image = session.query(ProductImages).one()
            self.assertTrue(image.url.startswith("https://storage.googleapis.com/"))
        finally:
            session.close()

    def test_unified_import_holic_creates_inactive_product(self):
        imported = ImportedProduct(
            provider="holic",
            source_url="https://holiclothing.com.ar/product/remera-1971/",
            title="Remera 1971",
            description="Remera de ribb manga larga",
            price=9400,
            cod_product="holic-r3846b-1-remera-1971",
            image_urls=["https://holiclothing.com.ar/wp-content/uploads/main.jpg"],
            category_slug="remeras",
            colors=["Negro"],
        )

        with patch.object(main, "fetch_product", return_value=imported):
            response = self.client.post(
                "/api/proveedores/importar",
                json={"url": imported.source_url, "status": False},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["created"])
        self.assertEqual(body["provider"], "holic")

        session = self.SessionLocal()
        try:
            product = session.query(Products).one()
            self.assertFalse(product.status)
            self.assertEqual(product.provider, "holic")
        finally:
            session.close()

    def test_import_failure_returns_ok_false_without_http_400(self):
        with patch.object(
            main,
            "fetch_product",
            side_effect=ProviderImportError(
                "So Chic limitó las consultas (demasiados pedidos). "
                "Esperá unos minutos e intentá de nuevo.",
                code="rate_limit",
            ),
        ):
            response = self.client.post(
                "/api/proveedores/importar",
                json={"url": "https://sochic.com.ar/product/campera-test/"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error_code"], "rate_limit")
        self.assertIn("limitó las consultas", body["error"])

    def test_favicon_is_served(self):
        response = self.client.get("/favicon.ico")
        self.assertEqual(response.status_code, 200)
        self.assertIn("image", response.headers.get("content-type", ""))

    @patch.object(main, "_nissie_bulk_import_task")
    def test_nissie_bulk_import_starts_run(self, mock_task):
        response = self.client.post("/api/proveedores/nissie/importar-masivo")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["provider"], "nissie")
        self.assertEqual(body["status"], "running")
        mock_task.assert_called_once()

        session = self.SessionLocal()
        try:
            run = session.query(ProviderImportRun).one()
            self.assertEqual(run.provider, "nissie")
            self.assertEqual(run.status, "running")
        finally:
            session.close()

    @patch.object(main, "_holic_bulk_import_task")
    def test_holic_bulk_import_starts_run(self, mock_task):
        response = self.client.post("/api/proveedores/holic/importar-masivo")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["provider"], "holic")
        self.assertEqual(body["status"], "running")
        mock_task.assert_called_once()

        session = self.SessionLocal()
        try:
            run = session.query(ProviderImportRun).one()
            self.assertEqual(run.provider, "holic")
            self.assertEqual(run.status, "running")
        finally:
            session.close()

    def test_product_list_provider_filter(self):
        session = self.SessionLocal()
        session.add(
            Products(
                item_title="Nissie Item",
                price=1000,
                cod_product="nissie-1",
                name="Nissie",
                status=False,
                provider="nissie",
            )
        )
        session.add(
            Products(
                item_title="Manual Item",
                price=1000,
                cod_product="manual-1",
                name="Manual",
                status=True,
                provider=None,
            )
        )
        session.commit()
        session.close()

        main.app.dependency_overrides[main.get_optional_user] = lambda: {"sub": "admin"}
        try:
            response = self.client.get(
                "/api/productos?status_filter=todos&provider=nissie",
            )
        finally:
            main.app.dependency_overrides.pop(main.get_optional_user, None)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["items"][0]["provider"], "nissie")


if __name__ == "__main__":
    unittest.main()
