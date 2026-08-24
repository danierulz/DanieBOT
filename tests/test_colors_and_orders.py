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
        self.category_id = cat.category_id
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
        self.admin_headers = {
            "Authorization": "Bearer "
            + main.create_access_token({"sub": main.ADMIN_USER["username"], "rol": "admin"})
        }
        self._notify_patch = patch("services.order_service.notify_advisor_new_web_order")
        self._notify_patch.start()
        self.addCleanup(self._notify_patch.stop)

    def tearDown(self):
        main.app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)

    def test_normalize_color_code(self):
        self.assertEqual(normalize_color_code("Verde musgo"), "VERDE_MUSGO")

    def test_list_colors_public(self):
        r = self.client.get("/api/colors")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(any(c["code"] == "CELESTE" for c in r.json()))

    def test_admin_list_colors_includes_product_usage(self):
        r = self.client.get("/api/admin/colors", headers=self.admin_headers)
        self.assertEqual(r.status_code, 200, r.text)
        celeste = next(c for c in r.json() if c["code"] == "CELESTE")
        self.assertEqual(celeste["product_count"], 1)
        self.assertEqual(celeste["products"][0]["product_id"], self.product_id)
        self.assertEqual(celeste["products"][0]["title"], "Remera Test")

    def test_admin_list_colors_requires_auth(self):
        r = self.client.get("/api/admin/colors")
        self.assertIn(r.status_code, (401, 403))

    def test_admin_create_color(self):
        r = self.client.post(
            "/api/admin/colors",
            json={"label": "Verde musgo", "hex": "#16A34A"},
            headers=self.admin_headers,
        )
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(data["color"]["label"], "Verde musgo")
        self.assertEqual(data["color"]["hex"], "#16A34A")
        self.assertTrue(data["created"])

    def test_admin_create_duplicate_color_returns_409(self):
        r = self.client.post(
            "/api/admin/colors",
            json={"label": "Celeste", "hex": "#38BDF8"},
            headers=self.admin_headers,
        )
        self.assertEqual(r.status_code, 409, r.text)
        self.assertIn("Celeste", r.json()["detail"])

    def test_admin_update_color_hex(self):
        r = self.client.put(
            f"/api/admin/colors/{self.color_id}",
            json={"hex": "#DC2626"},
            headers=self.admin_headers,
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["color"]["hex"], "#DC2626")

    def test_admin_delete_color_blocked_when_in_use(self):
        r = self.client.delete(
            f"/api/admin/colors/{self.color_id}",
            headers=self.admin_headers,
        )
        self.assertEqual(r.status_code, 409, r.text)
        detail = r.json()["detail"].lower()
        self.assertIn("producto", detail)
        self.assertIn("remera test", detail)

    def test_admin_delete_color_ok_when_unused(self):
        r = self.client.post(
            "/api/admin/colors",
            json={"label": "Rosa", "hex": "#EC4899"},
            headers=self.admin_headers,
        )
        self.assertEqual(r.status_code, 200, r.text)
        color_id = r.json()["color"]["color_id"]
        deleted = self.client.delete(
            f"/api/admin/colors/{color_id}",
            headers=self.admin_headers,
        )
        self.assertEqual(deleted.status_code, 200, deleted.text)

    def test_producto_includes_colores(self):
        r = self.client.get(f"/api/producto/{self.product_id}")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data["colores"]), 1)
        self.assertEqual(data["colores"][0]["label"], "Celeste")
        self.assertEqual(len(data["variantes"]), 1)
        self.assertTrue(data["variantes"][0]["disponible"])
        self.assertIsNone(data["variantes"][0]["color_id"])

    def test_update_product_variants_with_color_matrix(self):
        r = self.client.put(
            f"/api/productos/{self.product_id}",
            data={
                "item_title": "Remera Test",
                "price": "10000",
                "description": "Desc",
                "status": "1",
                "category_id": str(self.category_id),
                "colors_json": f"[{self.color_id}]",
                "variants_json": (
                    '[{"size_code":"M","color_id":'
                    + str(self.color_id)
                    + ',"qty_stock_local":2,"encargo_habilitado":false}]'
                ),
            },
            headers=self.admin_headers,
        )
        self.assertEqual(r.status_code, 200, r.text)
        detail = self.client.get(f"/api/producto/{self.product_id}").json()
        self.assertEqual(len(detail["variantes"]), 1)
        self.assertEqual(detail["variantes"][0]["color_id"], self.color_id)
        self.assertEqual(detail["variantes"][0]["qty_stock_local"], 2)

    def test_order_rejects_color_variant_mismatch(self):
        session = self.SessionLocal()
        rojo = Color(code="ROJO", label="Rojo", sort_order=20, hex="#FF0000")
        session.add(rojo)
        session.flush()
        size = session.query(Size).filter_by(code="M").first()
        product = session.query(Products).filter_by(product_id=self.product_id).first()
        session.add(
            ProductColor(product_id=product.product_id, color_id=rojo.color_id, activo=True)
        )
        session.add(
            ProductVariant(
                product_id=product.product_id,
                size_id=size.size_id,
                color_id=rojo.color_id,
                qty_stock_local=1,
                encargo_habilitado=False,
                activo=True,
            )
        )
        session.commit()
        rojo_variant = (
            session.query(ProductVariant)
            .filter_by(product_id=self.product_id, color_id=rojo.color_id)
            .first()
        )
        rojo_variant_id = rojo_variant.variant_id
        session.close()

        r = self.client.post(
            "/api/whatsapp/pedido",
            json={
                "items": [
                    {
                        "id": self.product_id,
                        "titulo": "Remera Test",
                        "precio": 10000,
                        "cantidad": 1,
                        "variant_id": rojo_variant_id,
                        "color_id": self.color_id,
                    }
                ],
            },
        )
        self.assertEqual(r.status_code, 400)

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
