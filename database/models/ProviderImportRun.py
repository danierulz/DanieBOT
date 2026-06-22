from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.orm import relationship

from database.init_db import Base


class ProviderImportRun(Base):
    __tablename__ = "provider_import_runs"

    run_id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(32), nullable=False, index=True)
    status = Column(String(16), nullable=False, default="running")
    phase = Column(String(16), nullable=False, default="discovering")
    progress_detail = Column(String(255), nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    discovered = Column(Integer, nullable=False, default=0)
    created = Column(Integer, nullable=False, default=0)
    skipped = Column(Integer, nullable=False, default=0)
    failed = Column(Integer, nullable=False, default=0)
    triggered_by = Column(String(128), nullable=True)

    items = relationship(
        "ProviderImportRunItem",
        back_populates="run",
        cascade="all, delete-orphan",
    )
