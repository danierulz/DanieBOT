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

    def test_build_database_url_cloud_sql_socket(self):
        import os

        from database import db_url

        old = {
            k: os.environ.get(k)
            for k in (
                "DATABASE_URL",
                "CLOUD_SQL_CONNECTION_NAME",
                "DB_HOST",
                "DB_USER",
                "DB_PASSWORD",
                "DB_NAME",
            )
        }
        try:
            os.environ.pop("DATABASE_URL", None)
            os.environ["CLOUD_SQL_CONNECTION_NAME"] = (
                "laslocaswhatsapp:us-central1:laslocas-dbng"
            )
            os.environ["DB_HOST"] = "10.0.0.1"
            os.environ["DB_USER"] = "bot"
            os.environ["DB_PASSWORD"] = "secret"
            os.environ["DB_NAME"] = "laslocas_dbng"
            url = db_url.build_database_url()
            args = db_url.get_sqlalchemy_connect_args()
            self.assertIn("@/laslocas_dbng", url)
            self.assertNotIn("10.0.0.1", url)
            self.assertIn("unix_sock", args)
            self.assertIn("laslocaswhatsapp:us-central1:laslocas-dbng", args["unix_sock"])
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
