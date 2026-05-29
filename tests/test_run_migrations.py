import os
import unittest

os.environ.setdefault("SKIP_DB_MIGRATIONS", "1")

from database.run_migrations import _migrations_disabled, apply_pending_migrations


class RunMigrationsTest(unittest.TestCase):
    def test_skip_when_env_set(self):
        os.environ["SKIP_DB_MIGRATIONS"] = "1"
        self.assertTrue(_migrations_disabled())
        del os.environ["SKIP_DB_MIGRATIONS"]

    def test_apply_noop_when_disabled(self):
        os.environ["SKIP_DB_MIGRATIONS"] = "1"
        apply_pending_migrations()  # no debe lanzar
        del os.environ["SKIP_DB_MIGRATIONS"]


if __name__ == "__main__":
    unittest.main()
