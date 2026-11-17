from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint

from database.init_db import Base


class ProductSourceUrl(Base):
    """Extra listing URL for a product that already has provider_source_url."""

    __tablename__ = "product_source_urls"
    __table_args__ = (
        UniqueConstraint("source_url", name="uq_product_source_urls_source_url"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(
        Integer,
        ForeignKey("products.product_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_url = Column(String(512), nullable=False)
