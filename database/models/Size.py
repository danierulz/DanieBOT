from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from database.init_db import Base


class Size(Base):
    __tablename__ = "sizes"

    size_id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(32), unique=True, nullable=False, index=True)
    label = Column(String(64), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    size_group = Column(String(16), nullable=False, default="letter", server_default="letter")

    variants = relationship("ProductVariant", back_populates="size")
