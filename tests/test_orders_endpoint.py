import os
import unittest

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

    def test_empty_cart_400(self):
        response = self.client.post("/api/whatsapp/pedido", json={"items": []})
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
