import os
import unittest

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
from auth.auth import create_access_token
from database.init_db import Base
from database.models.Products import Products


class ProductStatusApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(self.engine)

        session = self.SessionLocal()
        session.add(
            Products(
                item_title="Activo",
                price=1000,
                cod_product="A1",
                name="Activo",
                sku=1,
                description="d",
                status=True,
            )
        )
        session.add(
            Products(
                item_title="Inactivo",
                price=2000,
                cod_product="I1",
                name="Inactivo",
                sku=2,
                description="d",
                status=False,
            )
        )
        session.commit()
        session.close()

        def override_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        main.app.dependency_overrides[main.get_db_fastApi] = override_db
        self.client = TestClient(main.app)
        self.admin_headers = {
            "Authorization": "Bearer "
            + create_access_token({"sub": "admin", "rol": "admin"})
        }

    def tearDown(self):
        main.app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)

    def test_public_list_only_active(self):
        r = self.client.get("/api/productos")
        self.assertEqual(r.status_code, 200)
        titles = [x["titulo"] for x in r.json()["items"]]
        self.assertIn("Activo", titles)
        self.assertNotIn("Inactivo", titles)

    def test_admin_list_todos_with_token(self):
        r = self.client.get(
            "/api/productos?status_filter=todos",
            headers=self.admin_headers,
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["total"], 2)

    def test_status_filter_requires_auth(self):
        r = self.client.get("/api/productos?status_filter=todos")
        self.assertEqual(r.status_code, 403)

    def test_inactive_detail_hidden_without_auth(self):
        session = self.SessionLocal()
        inactive_id = session.query(Products).filter(Products.cod_product == "I1").one().product_id
        session.close()
        r = self.client.get(f"/api/producto/{inactive_id}")
        self.assertEqual(r.status_code, 404)

    def test_inactive_detail_visible_with_auth(self):
        session = self.SessionLocal()
        inactive_id = session.query(Products).filter(Products.cod_product == "I1").one().product_id
        session.close()
        r = self.client.get(f"/api/producto/{inactive_id}", headers=self.admin_headers)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["activo"])

    def test_create_product_rejects_long_description(self):
        long_desc = "x" * 256
        r = self.client.post(
            "/api/productos",
            data={
                "item_title": "Remera",
                "price": "1000",
                "description": long_desc,
            },
            headers=self.admin_headers,
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("256", r.json()["detail"])
        self.assertIn("255", r.json()["detail"])

    def test_update_product_rejects_long_description(self):
        session = self.SessionLocal()
        product_id = session.query(Products).filter(Products.cod_product == "A1").one().product_id
        session.close()
        r = self.client.put(
            f"/api/productos/{product_id}",
            data={
                "item_title": "Activo",
                "price": "1000",
                "description": "y" * 300,
            },
            headers=self.admin_headers,
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("300", r.json()["detail"])
        self.assertIn("descripción", r.json()["detail"].lower())

    def test_import_respects_status_flag(self):
        from provider_importers.types import ImportedProduct
        from unittest.mock import patch

        imported = ImportedProduct(
            provider="sochic",
            source_url="https://sochic.com.ar/product/x/",
            title="Nuevo activo",
            description="d",
            price=5000,
            cod_product="sochic-test-active",
            image_urls=[],
        )
        main.app.dependency_overrides[main.get_current_user] = lambda: {"sub": "admin"}

        with patch.object(main, "fetch_product", return_value=imported):
            r = self.client.post(
                "/api/proveedores/importar",
                json={"url": imported.source_url, "status": True},
                headers=self.admin_headers,
            )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["activo"])

        session = self.SessionLocal()
        try:
            p = session.query(Products).filter(Products.cod_product == "sochic-test-active").one()
            self.assertTrue(p.status)
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()
