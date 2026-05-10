from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship

from database.init_db import Base


class Category(Base):
    __tablename__ = "categories"

    category_id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    activo = Column(Boolean, nullable=False, default=True)

    products = relationship("Products", back_populates="category")
