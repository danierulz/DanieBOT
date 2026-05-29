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
from database.models.Color import Color
from database.models.ProductColor import ProductColor
from database.models.ProductVariant import ProductVariant
from database.models.Products import Products
from database.models.Size import Size
from services.colors import normalize_color_code
from services.order_service import build_whatsapp_message


class ColorsAndOrdersTest(unittest.TestCase):
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
        celeste = Color(code="CELESTE", label="Celeste", sort_order=10)
        session.add(celeste)
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
        session.add(
            ProductColor(product_id=product.product_id, color_id=celeste.color_id, activo=True)
        )
        session.commit()
        self.product_id = product.product_id
        self.color_id = celeste.color_id
        variant = session.query(ProductVariant).filter_by(product_id=product.product_id).first()
        self.variant_id = variant.variant_id
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

    def test_normalize_color_code(self):
        self.assertEqual(normalize_color_code("Verde musgo"), "VERDE_MUSGO")

    def test_list_colors_public(self):
        r = self.client.get("/api/colors")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(any(c["code"] == "CELESTE" for c in r.json()))

    def test_admin_create_color(self):
        token = main.create_access_token({"sub": main.ADMIN_USER["username"], "rol": "admin"})
        r = self.client.post(
            "/api/admin/colors",
            json={"label": "Verde musgo"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["color"]["label"], "Verde musgo")

    def test_producto_includes_colores(self):
        r = self.client.get(f"/api/producto/{self.product_id}")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data["colores"]), 1)
        self.assertEqual(data["colores"][0]["label"], "Celeste")

    def test_order_requires_color_when_product_has_colors(self):
        r = self.client.post(
            "/api/whatsapp/pedido",
            json={
                "items": [
                    {
                        "id": self.product_id,
                        "titulo": "Remera Test",
                        "precio": 10000,
                        "cantidad": 1,
                        "variant_id": self.variant_id,
                    }
                ],
            },
        )
        self.assertEqual(r.status_code, 400)

    def test_order_with_color_in_whatsapp_message(self):
        r = self.client.post(
            "/api/whatsapp/pedido",
            json={
                "items": [
                    {
                        "id": self.product_id,
                        "titulo": "Remera Test",
                        "precio": 10000,
                        "cantidad": 1,
                        "variant_id": self.variant_id,
                        "color_id": self.color_id,
                    }
                ],
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        mensaje = r.json()["mensaje"]
        self.assertIn("Talle M", mensaje)
        self.assertIn("Color Celeste", mensaje)

    def test_build_whatsapp_message_line_options(self):
        msg = build_whatsapp_message(
            "OJ-TEST-0001",
            [
                {
                    "title_snapshot": "Remera",
                    "size_label_snapshot": "M",
                    "color_label_snapshot": "Celeste",
                    "quantity": 1,
                    "unit_price": 10000,
                    "subtotal": 10000,
                }
            ],
            10000,
        )
        self.assertIn("Talle M — Color Celeste", msg)


if __name__ == "__main__":
    unittest.main()
