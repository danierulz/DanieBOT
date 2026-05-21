import os
import unittest

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "test")


class AlembicConfigTest(unittest.TestCase):
    def test_baseline_revision_is_head(self):
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        cfg = Config("alembic.ini")
        script = ScriptDirectory.from_config(cfg)
        self.assertEqual(script.get_heads(), ["20260520_0001"])

    def test_env_imports_metadata(self):
        import database.models  # noqa: F401
        from database.init_db import Base

        tables = set(Base.metadata.tables.keys())
        expected = {
            "categories",
            "sizes",
            "customers",
            "home_banners",
            "products",
            "orders",
            "product_images",
            "product_variants",
            "order_items",
            "order_events",
        }
        self.assertTrue(expected.issubset(tables), tables - expected)

    def test_build_database_url_from_env(self):
        from database.db_url import build_database_url

        url = build_database_url()
        self.assertIn("postgresql", url)


if __name__ == "__main__":
    unittest.main()
