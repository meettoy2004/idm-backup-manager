from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from sqlalchemy.sql import func
from ..config.database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id          = Column(Integer, primary_key=True, index=True)
    timestamp   = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    user        = Column(String, nullable=False, default="system")
    auth_method = Column(String, nullable=True)
    action      = Column(String, nullable=False, index=True)
    resource    = Column(String, nullable=True)
    resource_id = Column(String, nullable=True)
    detail      = Column(Text, nullable=True)
    extra_data  = Column(JSON, nullable=True)   # renamed from 'metadata' (reserved by SQLAlchemy)
    ip_address  = Column(String, nullable=True)
    status      = Column(String, default="success")
