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


class SizesAdminTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(self.engine)

        session = self.SessionLocal()
        session.add(Size(code="M", label="M", sort_order=30, size_group="letter"))
        session.add(Category(slug="remeras", name="Remeras", sort_order=10, activo=True, size_group="letter"))
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
            + main.create_access_token({"sub": main.ADMIN_USER["username"], "rol": "admin"})
        }

    def tearDown(self):
        main.app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)

    def test_admin_create_size(self):
        r = self.client.post(
            "/api/admin/sizes",
            json={"code": "XL", "label": "XL", "size_group": "letter", "sort_order": 50},
            headers=self.admin_headers,
        )
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(data["size"]["code"], "XL")
        self.assertTrue(data["created"])

    def test_admin_create_duplicate_size_returns_409(self):
        r = self.client.post(
            "/api/admin/sizes",
            json={"code": "M", "label": "M", "size_group": "letter"},
            headers=self.admin_headers,
        )
        self.assertEqual(r.status_code, 409, r.text)

    def test_admin_delete_size_in_use_returns_409(self):
        session = self.SessionLocal()
        size = session.query(Size).filter_by(code="M").first()
        cat = session.query(Category).first()
        product = Products(item_title="Test", price=1000, status=True, category_id=cat.category_id)
        session.add(product)
        session.flush()
        session.add(
            ProductVariant(
                product_id=product.product_id,
                size_id=size.size_id,
                qty_stock_local=1,
                encargo_habilitado=False,
                activo=True,
            )
        )
        session.commit()
        size_id = size.size_id
        session.close()

        r = self.client.delete(f"/api/admin/sizes/{size_id}", headers=self.admin_headers)
        self.assertEqual(r.status_code, 409, r.text)

    def test_admin_update_category_size_group(self):
        session = self.SessionLocal()
        cat = session.query(Category).filter_by(slug="remeras").first()
        cat_id = cat.category_id
        session.close()

        r = self.client.put(
            f"/api/admin/categories/{cat_id}",
            json={"size_group": "numeric"},
            headers=self.admin_headers,
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["category"]["size_group"], "numeric")

    def test_admin_list_sizes(self):
        r = self.client.get("/api/admin/sizes", headers=self.admin_headers)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(any(row["code"] == "M" for row in r.json()))


if __name__ == "__main__":
    unittest.main()
