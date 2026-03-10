from sqlalchemy import Boolean, Column, DateTime, Integer, func
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
    cod_product = Column(String(20))
    item_title = Column(String(20))
    name = Column(String(35))
    sku = Column(Integer) 
    extract_date = Column(DateTime(timezone=True), server_default=func.now())
    create_date = Column(DateTime(timezone=True), server_default=func.now())

    images = relationship("ProductImages", back_populates="product")

    def __init__(self, description, price, status, #gallery_photos, 
                 cod_product,
                item_title, name, sku, extract_date):
           #self.product_id = product_id
        self.description = description
        self.price = price
        self.status = status
#        self.gallery_photos = gallery_photos
        self.cod_product = cod_product
        self.item_title = item_title
        self.name = name
        self.sku = sku
        self.extract_date = extract_date

    def __repr__(self) -> str:
        return f"User(product_id={self.product_id!r}, description={self.description!r}, unit_price={self.price!r})"


