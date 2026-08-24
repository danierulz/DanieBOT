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
from config import get_default_promo_banner_text
from database.init_db import Base


class PromoBannerTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(self.engine)

        def override_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        main.app.dependency_overrides[main.get_db_fastApi] = override_db
        self._orig_session_local = main.SessionLocal
        main.SessionLocal = self.SessionLocal
        self.client = TestClient(main.app)
        self.admin_headers = {
            "Authorization": "Bearer "
            + main.create_access_token({"sub": main.ADMIN_USER["username"], "rol": "admin"})
        }

    def tearDown(self):
        main.SessionLocal = self._orig_session_local
        main.app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)

    def test_admin_requires_auth(self):
        r = self.client.get("/api/admin/promo-banner")
        self.assertEqual(r.status_code, 401)

    def test_default_then_update_appears_on_home(self):
        r = self.client.get("/api/admin/promo-banner", headers=self.admin_headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["text"], get_default_promo_banner_text())
        self.assertTrue(r.json()["activo"])

        home = self.client.get("/")
        self.assertEqual(home.status_code, 200)
        self.assertIn(get_default_promo_banner_text(), home.text)

        saved = self.client.put(
            "/api/admin/promo-banner",
            headers=self.admin_headers,
            json={"text": "Envío gratis desde $80.000", "activo": True},
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["text"], "Envío gratis desde $80.000")

        home2 = self.client.get("/")
        self.assertIn("Envío gratis desde $80.000", home2.text)
        self.assertNotIn(get_default_promo_banner_text(), home2.text)

    def test_hidden_when_inactive(self):
        self.client.put(
            "/api/admin/promo-banner",
            headers=self.admin_headers,
            json={"text": "Solo staff", "activo": False},
        )
        home = self.client.get("/")
        self.assertNotIn("Solo staff", home.text)
        footer_pages = self.client.get("/contacto")
        self.assertNotIn("Solo staff", footer_pages.text)

    def test_rejects_too_long(self):
        r = self.client.put(
            "/api/admin/promo-banner",
            headers=self.admin_headers,
            json={"text": "x" * 201, "activo": True},
        )
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
