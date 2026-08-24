from sqlalchemy import Column, String, Text

from database.init_db import Base


class SiteSetting(Base):
    __tablename__ = "site_settings"

    key = Column(String(64), primary_key=True)
    value = Column(Text, nullable=True)
