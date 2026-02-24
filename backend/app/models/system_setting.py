from sqlalchemy import Column, Integer, String, Text, DateTime, func
from ..config.database import Base


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id         = Column(Integer, primary_key=True)
    key        = Column(String(255), unique=True, nullable=False, index=True)
    value      = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
