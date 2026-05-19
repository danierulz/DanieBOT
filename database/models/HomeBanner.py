from sqlalchemy import Boolean, Column, Integer, String

from database.init_db import Base


class HomeBanner(Base):
    __tablename__ = "home_banners"

    banner_id = Column(Integer, primary_key=True, autoincrement=True)
    image_url = Column(String(512), nullable=False)
    media_type = Column(String(16), nullable=False, default="image")
    title = Column(String(200), nullable=True)
    subtitle = Column(String(300), nullable=True)
    link_href = Column(String(512), nullable=False, default="/")
    sort_order = Column(Integer, nullable=False, default=0)
    activo = Column(Boolean, nullable=False, default=True)
