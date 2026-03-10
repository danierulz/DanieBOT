import datetime
from sqlalchemy import Column, Float, Integer, ForeignKey
from sqlalchemy.orm import relationship
from database.init_db import Base


class OrderItem(Base):
    __tablename__ = "order_items"
    order_item_id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.order_id"))
    product_id = Column(Integer, ForeignKey("products.product_id"))
    quantity = Column(Integer)
    unit_price = Column(Float)
    subtotal = Column(Float)

    order = relationship("Order", back_populates="items")
