import datetime

from sqlalchemy import Column, DateTime, Float, Integer, Text
from sqlalchemy import String
from sqlalchemy.orm import relationship
from database.init_db import Base


class Order(Base):
    __tablename__ = "orders"
    order_id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(String(32), default="pendiente", nullable=False)
    customer_name = Column(String(200), nullable=True)
    customer_phone = Column(String(50), nullable=True)
    total = Column(Float, default=0.0, nullable=False)
    note = Column(Text, nullable=True)



    items = relationship("OrderItem", back_populates="order")
