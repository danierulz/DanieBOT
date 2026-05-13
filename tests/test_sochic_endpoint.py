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
from database.models.Size import Size
from provider_importers.sochic import ImportedSoChicProduct


class SoChicEndpointTest(unittest.TestCase):
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

    def test_import_endpoint_creates_orderable_product_from_provider_data(self):
        imported = ImportedSoChicProduct(
            source_url="https://sochic.com.ar/product/campera-friza-young-leaders/",
            title="Campera Friza Young Leaders",
            description="MEDIDAS CONTORNO PECHO: 58",
            price=26100,
            original_price=29000,
            discount_percent=10,
            sku=3515,
            cod_product="sochic-3515-campera-friza-young-leaders",
            image_urls=[
                "https://sochic.com.ar/wp-content/uploads/main.jpeg",
                "https://sochic.com.ar/wp-content/uploads/detail.jpeg",
            ],
            category_slug="camperas",
            colors=["Celeste", "Rosa"],
        )

        with patch.object(main, "fetch_sochic_product", return_value=imported):
            response = self.client.post(
                "/api/proveedores/sochic/importar",
                json={"url": imported.source_url},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["created"], True)

        session = self.SessionLocal()
        try:
            product = session.query(Products).one()
            self.assertEqual(product.item_title, imported.title)
            self.assertEqual(product.price, 29000)
            self.assertTrue(product.is_sale)
            self.assertEqual(product.discount_percent, 10)
            self.assertIn("Colores proveedor: Celeste, Rosa", product.description)
            self.assertEqual(product.category.slug, "camperas")
            self.assertEqual(session.query(ProductImages).count(), 2)
            variant = session.query(ProductVariant).one()
            self.assertEqual(variant.qty_stock_local, 0)
            self.assertTrue(variant.encargo_habilitado)
            self.assertEqual(variant.size.code, "UNICO")
        finally:
            session.close()

    def test_import_endpoint_returns_existing_product_without_duplicate(self):
        imported = ImportedSoChicProduct(
            source_url="https://sochic.com.ar/product/campera-friza-young-leaders/",
            title="Campera Friza Young Leaders",
            description="MEDIDAS CONTORNO PECHO: 58",
            price=26100,
            original_price=29000,
            discount_percent=10,
            sku=3515,
            cod_product="sochic-3515-campera-friza-young-leaders",
            image_urls=[],
            category_slug="camperas",
            colors=[],
        )

        with patch.object(main, "fetch_sochic_product", return_value=imported):
            first = self.client.post("/api/proveedores/sochic/importar", json={"url": imported.source_url})
            second = self.client.post("/api/proveedores/sochic/importar", json={"url": imported.source_url})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["created"], False)

        session = self.SessionLocal()
        try:
            self.assertEqual(session.query(Products).count(), 1)
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()
