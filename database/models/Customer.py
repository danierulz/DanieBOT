from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from database.init_db import Base


class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(Integer, primary_key=True, autoincrement=True)
    wa_id = Column(String(32), unique=True, nullable=True, index=True)
    phone = Column(String(50), nullable=True)
    display_name = Column(String(200), nullable=True)
    email = Column(String(255), nullable=True)
    email_verified = Column(Boolean, nullable=False, default=False)
    marketing_email_consent = Column(Boolean, nullable=False, default=False)
    marketing_email_consent_at = Column(DateTime, nullable=True)
    marketing_whatsapp_consent = Column(Boolean, nullable=False, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    orders = relationship("Order", back_populates="customer")
