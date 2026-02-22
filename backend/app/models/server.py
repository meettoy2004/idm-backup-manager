from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..config.database import Base

class Server(Base):
    __tablename__ = "servers"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String, nullable=False)
    hostname    = Column(String, nullable=False)
    port        = Column(Integer, default=22)
    username    = Column(String, nullable=False)
    description = Column(String, nullable=True)
    is_active   = Column(Boolean, default=True)

    # Subscription manager status tracking
    subscription_status       = Column(String, nullable=True)
    subscription_message      = Column(String, nullable=True)
    subscription_last_checked = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Phase 1: Multi-tenancy
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)

    # Relationships
    backup_configs     = relationship("BackupConfig", back_populates="server", cascade="all, delete-orphan")
    backup_jobs        = relationship("BackupJob", back_populates="server", cascade="all, delete-orphan")
    organization       = relationship("Organization", back_populates="servers")
    restore_operations = relationship("RestoreOperation", back_populates="server")
