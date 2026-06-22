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
from database.models.Products import Products
from services.categories import list_categories_for_nav, list_categories_public


class CategoriesAdminTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(self.engine)

        session = self.SessionLocal()
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

    def test_admin_create_category(self):
        r = self.client.post(
            "/api/admin/categories",
            json={"name": "Enteritos", "slug": "enteritos", "size_group": "letter", "sort_order": 50},
            headers=self.admin_headers,
        )
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(data["category"]["slug"], "enteritos")
        self.assertTrue(data["created"])

    def test_admin_create_duplicate_slug_returns_409(self):
        r = self.client.post(
            "/api/admin/categories",
            json={"name": "Otra remera", "slug": "remeras", "size_group": "letter"},
            headers=self.admin_headers,
        )
        self.assertEqual(r.status_code, 409, r.text)

    def test_admin_delete_category_with_products_returns_409(self):
        session = self.SessionLocal()
        cat = session.query(Category).filter_by(slug="remeras").first()
        session.add(Products(item_title="Test", price=1000, status=True, category_id=cat.category_id))
        session.commit()
        cat_id = cat.category_id
        session.close()

        r = self.client.delete(f"/api/admin/categories/{cat_id}", headers=self.admin_headers)
        self.assertEqual(r.status_code, 409, r.text)

    def test_deactivated_category_not_in_public_api(self):
        session = self.SessionLocal()
        cat = session.query(Category).filter_by(slug="remeras").first()
        cat_id = cat.category_id
        session.close()

        r = self.client.put(
            f"/api/admin/categories/{cat_id}",
            json={"activo": False},
            headers=self.admin_headers,
        )
        self.assertEqual(r.status_code, 200, r.text)

        public = self.client.get("/api/categories")
        self.assertEqual(public.status_code, 200)
        self.assertFalse(any(c["slug"] == "remeras" for c in public.json()))

    def test_nav_helper_returns_only_active_ordered(self):
        session = self.SessionLocal()
        session.add(Category(slug="jeans", name="Jeans", sort_order=5, activo=True, size_group="numeric"))
        session.add(Category(slug="oculta", name="Oculta", sort_order=1, activo=False, size_group="letter"))
        session.commit()
        nav = list_categories_for_nav(session)
        public = list_categories_public(session)
        session.close()

        slugs = [c["slug"] for c in nav]
        self.assertEqual(slugs, ["jeans", "remeras"])
        self.assertEqual([c["slug"] for c in public], ["jeans", "remeras"])

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


if __name__ == "__main__":
    unittest.main()
