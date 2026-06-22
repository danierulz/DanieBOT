import os
import unittest
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "test")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database.models  # noqa: F401
from database.init_db import Base
from database.models.ProviderImportRun import ProviderImportRun
from services.provider_import_runs import cancel_run, is_run_stale, serialize_run


class ProviderImportRunsTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        Base.metadata.drop_all(self.engine)

    def test_serialize_run_includes_phase_and_progress_detail(self):
        session = self.SessionLocal()
        run = ProviderImportRun(
            provider="nissie",
            status="running",
            phase="discovering",
            progress_detail="Nissie · listado · página 2",
            discovered=12,
        )
        session.add(run)
        session.commit()
        session.refresh(run)

        payload = serialize_run(session, run)
        self.assertEqual(payload["phase"], "discovering")
        self.assertEqual(payload["progress_detail"], "Nissie · listado · página 2")
        self.assertEqual(payload["discovered"], 12)
        self.assertEqual(payload["processed"], 0)
        self.assertFalse(payload["is_stale"])
        session.close()

    def test_is_run_stale_after_two_hours(self):
        session = self.SessionLocal()
        run = ProviderImportRun(
            provider="laslocas",
            status="running",
            phase="importing",
            started_at=datetime.now(timezone.utc) - timedelta(hours=3),
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        self.assertTrue(is_run_stale(run))
        session.close()

    def test_cancel_run_marks_failed(self):
        session = self.SessionLocal()
        run = ProviderImportRun(provider="holic", status="running", phase="importing")
        session.add(run)
        session.commit()
        session.refresh(run)
        cancel_run(session, run, reason="Cancelada manualmente")
        session.refresh(run)
        self.assertEqual(run.status, "failed")
        self.assertEqual(run.phase, "failed")
        self.assertEqual(run.progress_detail, "Cancelada manualmente")
        self.assertIsNotNone(run.finished_at)
        session.close()


if __name__ == "__main__":
    unittest.main()
