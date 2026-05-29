from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, func
from sqlalchemy import String
from sqlalchemy.orm import relationship
from database.init_db import Base


class Products(Base):
    __tablename__ = "products"
    product_id = Column(Integer, primary_key=True, autoincrement=True)
    description = Column(String(255))
    price = Column(Integer)
    status = Column(Boolean, default=False)
#    gallery_photos = Column(ARRAY(String(512)), nullable=True)
    cod_product = Column(String(50))
    item_title = Column(String(255))
    name = Column(String(80))
    sku = Column(Integer)
    category_id = Column(
        Integer,
        ForeignKey("categories.category_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_sale = Column(Boolean, nullable=False, default=False)
    discount_percent = Column(Integer, nullable=True)
    extract_date = Column(DateTime(timezone=True), server_default=func.now())
    create_date = Column(DateTime(timezone=True), server_default=func.now())

    images = relationship("ProductImages", back_populates="product")
    variants = relationship(
        "ProductVariant",
        back_populates="product",
        cascade="all, delete-orphan",
    )
    product_colors = relationship(
        "ProductColor",
        back_populates="product",
        cascade="all, delete-orphan",
    )
    category = relationship("Category", back_populates="products")


 
    def __repr__(self) -> str:
        return f"User(product_id={self.product_id!r}, description={self.description!r}, unit_price={self.price!r})"


