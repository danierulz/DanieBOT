from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from database.init_db import Base


class Color(Base):
    __tablename__ = "colors"

    color_id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(32), unique=True, nullable=False, index=True)
    label = Column(String(64), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    hex = Column(String(7), nullable=True)

    product_links = relationship("ProductColor", back_populates="color", cascade="all, delete-orphan")
