import datetime
from typing import List
from sqlalchemy import ARRAY, Boolean, Column, DateTime, ForeignKey, Integer, func
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class Products(Base):
    __tablename__ = "products"
    product_id = Column(Integer, primary_key=True, autoincrement=True)
    description = Column(String(255))
    price = Column(Integer)
    status = Column(Boolean, default=False)
    gallery_photos = Column(ARRAY(String(512)), nullable=True)
    cod_product = Column(String(20))
    item_title = Column(String(20))
    name = Column(String(35))
    sku = Column(Integer)
    extract_date = Column(DateTime(timezone=True), server_default=func.now())
    create_date = Column(DateTime(timezone=True), server_default=func.now())

    def __init__(self, description, price, status, gallery_photos, cod_product,
                item_title, name, extract_date):
           #self.product_id = product_id
        self.description = description
        self.price = price
        self.status = status
        self.gallery_photos = gallery_photos
        self.cod_product = cod_product
        self.item_title = item_title
        self.name = name
        self.extract_date = extract_date

    def __repr__(self) -> str:
        return f"User(product_id={self.product_id!r}, description={self.description!r}, unit_price={self.unit_price!r})"

class ProductImage(Base):
    __tablename__ = 'product_images'

    image_id = Column(Integer, primary_key=True)
    # La llave foránea que apunta al ID del producto
    product_id = Column(Integer, ForeignKey('products.product_id'))
    filename = Column(String(255), nullable=False) # Solo el nombre: "foto1.webp"
    is_main = Column(Boolean, default=False)       # Para saber cuál es la portada

    # Relación inversa: permite saber a qué producto pertenece la foto
    product = relationship("Products", back_populates="images")
