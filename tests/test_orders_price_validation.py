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
from database.init_db import Base
from database.models.Category import Category
from database.models.ProductVariant import ProductVariant
from database.models.Products import Products
from database.models.Size import Size


class OrdersPriceValidationTest(unittest.TestCase):
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
        session.add(Category(slug="remeras", name="Remeras", sort_order=10, activo=True))
        session.flush()
        cat = session.query(Category).first()
        product = Products(
            item_title="Remera Sale",
            price=10000,
            status=True,
            category_id=cat.category_id,
            is_sale=True,
            discount_percent=10,
        )
        session.add(product)
        session.flush()
        session.add(
            ProductVariant(
                product_id=product.product_id,
                size_id=size.size_id,
                qty_stock_local=10,
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

    def test_rejects_tampered_price(self):
        response = self.client.post(
            "/api/whatsapp/pedido",
            json={
                "items": [
                    {
                        "id": self.product_id,
                        "titulo": "Remera Sale",
                        "precio": 1,
                        "cantidad": 1,
                    }
                ],
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Precio no válido", response.json().get("detail", ""))

    def test_accepts_server_price(self):
        response = self.client.post(
            "/api/whatsapp/pedido",
            json={
                "items": [
                    {
                        "id": self.product_id,
                        "titulo": "Remera Sale",
                        "precio": 9000,
                        "cantidad": 1,
                    }
                ],
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["order_code"][:3], "OJ-")


if __name__ == "__main__":
    unittest.main()
