import os
import unittest

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "test")

from auth.auth import authenticate_admin, hash_admin_password


class AdminAuthTest(unittest.TestCase):
    def setUp(self):
        self._env = {
            "APP_DEBUG": os.environ.get("APP_DEBUG"),
            "ADMIN_USERNAME": os.environ.get("ADMIN_USERNAME"),
            "ADMIN_PASSWORD_HASH": os.environ.get("ADMIN_PASSWORD_HASH"),
            "ADMIN_PASSWORD": os.environ.get("ADMIN_PASSWORD"),
            "JWT_SECRET_KEY": os.environ.get("JWT_SECRET_KEY"),
        }
        os.environ["APP_DEBUG"] = "false"
        os.environ["ADMIN_USERNAME"] = "panel"
        os.environ["ADMIN_PASSWORD_HASH"] = hash_admin_password("MiClaveSegura123")
        os.environ.pop("ADMIN_PASSWORD", None)
        os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-for-unit-tests"

        import importlib
        import auth.auth as auth_module

        importlib.reload(auth_module)
        self.auth = auth_module

    def tearDown(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_authenticate_with_bcrypt_hash(self):
        self.assertTrue(self.auth.authenticate_admin("panel", "MiClaveSegura123"))
        self.assertFalse(self.auth.authenticate_admin("panel", "wrong"))
        self.assertFalse(self.auth.authenticate_admin("other", "MiClaveSegura123"))


if __name__ == "__main__":
    unittest.main()
