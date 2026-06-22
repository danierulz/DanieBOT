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
from database.models.Size import Size
from services.sizes import get_size_codes_for_category, get_size_group_for_category


class SizeGroupsDbTest(unittest.TestCase):
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
        session.add(Size(code="36", label="36", sort_order=76, size_group="numeric"))
        session.add(Size(code="38", label="38", sort_order=77, size_group="numeric"))
        session.add(Category(slug="jeans", name="Jeans", sort_order=10, activo=True, size_group="numeric"))
        session.add(Category(slug="remeras", name="Remeras", sort_order=20, activo=True, size_group="letter"))
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
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()
        main.app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)

    def test_jeans_uses_numeric_group(self):
        self.assertEqual(get_size_group_for_category(self.db, "jeans"), "numeric")
        codes = get_size_codes_for_category(self.db, "jeans")
        self.assertIn("36", codes)
        self.assertNotIn("M", codes)

    def test_remeras_uses_letter_group(self):
        self.assertEqual(get_size_group_for_category(self.db, "remeras"), "letter")
        codes = get_size_codes_for_category(self.db, "remeras")
        self.assertIn("M", codes)
        self.assertNotIn("36", codes)

    def test_unknown_category_defaults_to_letter(self):
        self.assertEqual(get_size_group_for_category(self.db, "otra"), "letter")

    def test_sizes_filtered_by_jeans_category(self):
        r = self.client.get("/api/sizes", params={"category_slug": "jeans"})
        self.assertEqual(r.status_code, 200)
        codes = {row["code"] for row in r.json()}
        self.assertEqual(codes, {"36", "38"})

    def test_sizes_unfiltered_returns_all(self):
        r = self.client.get("/api/sizes")
        self.assertEqual(r.status_code, 200)
        codes = {row["code"] for row in r.json()}
        self.assertEqual(codes, {"M", "36", "38"})


if __name__ == "__main__":
    unittest.main()
