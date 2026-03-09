from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from database.init_db import Base

class ProductImages(Base):
    __tablename__ = 'product_images'
 
    image_id = Column(Integer, primary_key=True)
    # La llave foránea que apunta al ID del producto
    product_id = Column(Integer, ForeignKey('products.product_id'))
    filename = Column(String(255), nullable=False) # Solo el nombre: "foto1.webp"
    url = Column(String(512), nullable=False)        # "https://storage.googleapis.com/mi-bucket/productos/camisa1.webp"
    is_main = Column(Boolean, default=False)       # Para saber cuál es la portada

    # Relación inversa: permite saber a qué producto pertenece la foto
    product = relationship("Products", back_populates="images")
