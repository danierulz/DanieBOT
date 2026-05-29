from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database.init_db import Base


class OrderItem(Base):
    __tablename__ = "order_items"

    order_item_id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.order_id", ondelete="CASCADE"))
    product_id = Column(Integer, ForeignKey("products.product_id"))
    variant_id = Column(
        Integer,
        ForeignKey("product_variants.variant_id", ondelete="SET NULL"),
        nullable=True,
    )
    color_id = Column(
        Integer,
        ForeignKey("colors.color_id", ondelete="SET NULL"),
        nullable=True,
    )
    size_label_snapshot = Column(String(64), nullable=True)
    color_label_snapshot = Column(String(64), nullable=True)
    title_snapshot = Column(String(255), nullable=True)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Float, nullable=False)
    subtotal = Column(Float, nullable=False)

    order = relationship("Order", back_populates="items")
