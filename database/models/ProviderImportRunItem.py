from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database.init_db import Base


class ProviderImportRunItem(Base):
    __tablename__ = "provider_import_run_items"

    item_id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(
        Integer,
        ForeignKey("provider_import_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_url = Column(String(512), nullable=False)
    cod_product = Column(String(50), nullable=True)
    status = Column(String(16), nullable=False)
    error_message = Column(String(512), nullable=True)
    product_id = Column(
        Integer,
        ForeignKey("products.product_id", ondelete="SET NULL"),
        nullable=True,
    )

    run = relationship("ProviderImportRun", back_populates="items")
