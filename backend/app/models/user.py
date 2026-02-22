from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..config.database import Base

class User(Base):
    __tablename__ = "users"

    id                       = Column(Integer, primary_key=True, index=True)
    email                    = Column(String, unique=True, index=True, nullable=False)
    username                 = Column(String, unique=True, index=True, nullable=False)
    full_name                = Column(String, nullable=True)
    hashed_password          = Column(String, nullable=True)
    role                     = Column(String, default="viewer")
    auth_method              = Column(String, default="local")
    oidc_subject             = Column(String, unique=True, nullable=True)
    is_active                = Column(Boolean, default=True)
    requires_password_change = Column(Boolean, default=False)
    last_login               = Column(DateTime(timezone=True), nullable=True)
    created_at               = Column(DateTime(timezone=True), server_default=func.now())

    # Phase 1: New relationships
    organizations         = relationship("UserOrganization", back_populates="user", cascade="all, delete-orphan")
    notification_settings = relationship("NotificationSetting", back_populates="user", cascade="all, delete-orphan")
    restore_operations    = relationship("RestoreOperation", back_populates="requester")
    dr_templates          = relationship("DRTemplate", back_populates="creator")
