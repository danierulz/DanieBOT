import os
import unittest
from unittest.mock import patch

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault("ORDER_CODE_PREFIX", "OJ")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database.models  # noqa: F401
import main
from database.init_db import Base
from database.models.Category import Category
from database.models.ProductVariant import ProductVariant
from database.models.Products import Products
from database.models.Size import Size


class OrdersEndpointTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(self.engine)

        session = self.SessionLocal()
        size = Size(code="M", label="M", sort_order=30)
        session.add(size)
        session.flush()
        cat = Category(slug="remeras", name="Remeras", sort_order=10, activo=True)
        session.add(cat)
        session.flush()
        product = Products(
            item_title="Remera Test",
            price=10000,
            status=True,
            category_id=cat.category_id,
        )
        session.add(product)
        session.flush()
        session.add(
            ProductVariant(
                product_id=product.product_id,
                size_id=size.size_id,
                qty_stock_local=5,
                encargo_habilitado=False,
                activo=True,
            )
        )
        session.commit()
        self.product_id = product.product_id
        session.close()

        def override_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        main.app.dependency_overrides[main.get_db_fastApi] = override_db
        self.client = TestClient(main.app)
        self._notify_patch = patch("services.order_service.notify_advisor_new_web_order")
        self._notify_mock = self._notify_patch.start()
        self.addCleanup(self._notify_patch.stop)

    def tearDown(self):
        main.app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)

    def test_create_order_returns_code_and_message(self):
        response = self.client.post(
            "/api/whatsapp/pedido",
            json={
                "items": [
                    {
                        "id": self.product_id,
                        "titulo": "Remera Test",
                        "precio": 10000,
                        "cantidad": 2,
                    }
                ],
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertRegex(data["order_code"], r"^OJ-\d{8}-[A-HJ-NP-Z2-9]{4}$")
        self.assertIn(data["order_code"], data["mensaje"])
        self.assertIn("whatsapp_number", data)
        self.assertFalse(data.get("reused"))

    def test_same_cart_reuses_order_and_notifies_once(self):
        payload = {
            "items": [
                {
                    "id": self.product_id,
                    "titulo": "Remera Test",
                    "precio": 10000,
                    "cantidad": 2,
                }
            ],
        }
        first = self.client.post("/api/whatsapp/pedido", json=payload)
        second = self.client.post("/api/whatsapp/pedido", json=payload)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(first.json()["order_code"], second.json()["order_code"])
        self.assertFalse(first.json()["reused"])
        self.assertTrue(second.json()["reused"])
        self.assertEqual(self._notify_mock.call_count, 1)

    def test_unknown_product_is_rejected(self):
        response = self.client.post(
            "/api/whatsapp/pedido",
            json={
                "items": [
                    {
                        "id": 99999,
                        "titulo": "Remera Test",
                        "precio": 10000,
                        "cantidad": 1,
                    }
                ],
            },
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("no encontrado", response.json()["detail"].lower())

    def test_empty_cart_400(self):
        response = self.client.post("/api/whatsapp/pedido", json={"items": []})
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
