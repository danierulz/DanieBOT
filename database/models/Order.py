from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import JSON
from sqlalchemy.orm import relationship

from database.init_db import Base


class Order(Base):
    __tablename__ = "orders"

    order_id = Column(Integer, primary_key=True, index=True)
    order_code = Column(String(32), unique=True, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(String(32), default="pendiente", nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.customer_id"), nullable=True)
    customer_name = Column(String(200), nullable=True)
    customer_phone = Column(String(50), nullable=True)
    whatsapp_wa_id = Column(String(32), nullable=True, index=True)
    source = Column(String(32), default="web", nullable=False)
    channel = Column(String(32), default="wa_me", nullable=False)
    total = Column(Float, default=0.0, nullable=False)
    note = Column(Text, nullable=True)
    cart_snapshot = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    confirmed_at = Column(DateTime, nullable=True)

    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    events = relationship("OrderEvent", back_populates="order", cascade="all, delete-orphan")
