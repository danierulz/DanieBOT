from sqlalchemy import Boolean, Column, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from database.init_db import Base


class ProductColor(Base):
    __tablename__ = "product_colors"
    __table_args__ = (
        UniqueConstraint("product_id", "color_id", name="uq_product_colors_product_color"),
    )

    product_color_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(
        Integer,
        ForeignKey("products.product_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    color_id = Column(
        Integer,
        ForeignKey("colors.color_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    activo = Column(Boolean, nullable=False, default=True)

    product = relationship("Products", back_populates="product_colors")
    color = relationship("Color", back_populates="product_links")
