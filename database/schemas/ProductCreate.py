from typing import Optional

from pydantic import BaseModel
from datetime import datetime

class ProductImageCreate(BaseModel):
    url: str

class ProductCreate(BaseModel):
    description: str
    price: int
    status: Optional[bool] = None
    cod_product: Optional[str] = None
    item_title: str
    name: Optional[str] = None
    sku: Optional[int] = None
    images: list[ProductImageCreate] = []

class ProductImageOut(BaseModel):
    id: int
    url: str
    class Config:
        orm_mode = True

class ProductOut(ProductCreate):
    product_id: int
    extract_date: datetime
    create_date: datetime

    class Config:
        orm_mode = True