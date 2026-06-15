from sqlalchemy import Boolean, Column, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from database.init_db import Base


class ProductVariant(Base):
    __tablename__ = "product_variants"
    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "size_id",
            "color_id",
            name="uq_product_variants_product_size_color",
        ),
    )

    variant_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(
        Integer,
        ForeignKey("products.product_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    size_id = Column(Integer, ForeignKey("sizes.size_id"), nullable=False, index=True)
    color_id = Column(Integer, ForeignKey("colors.color_id"), nullable=True, index=True)
    qty_stock_local = Column(Integer, nullable=False, default=0)
    encargo_habilitado = Column(Boolean, nullable=False, default=False)
    dias_encargo_estimados = Column(Integer, nullable=True)
    activo = Column(Boolean, nullable=False, default=True)

    product = relationship("Products", back_populates="variants")
    size = relationship("Size", back_populates="variants")
    color = relationship("Color", back_populates="variants")
