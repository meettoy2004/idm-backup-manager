from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.config.database import Base

if TYPE_CHECKING:
    from app.models.server import Server
    from app.models.backup_config import BackupConfig
    from app.models.user import User
    from app.models.notification_setting import NotificationSetting
    from app.models.dr_template import DRTemplate


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    servers: Mapped[List["Server"]] = relationship("Server", back_populates="organization")
    backup_configs: Mapped[List["BackupConfig"]] = relationship("BackupConfig", back_populates="organization")
    members: Mapped[List["UserOrganization"]] = relationship("UserOrganization", back_populates="organization", cascade="all, delete-orphan")
    notification_settings: Mapped[List["NotificationSetting"]] = relationship("NotificationSetting", back_populates="organization")
    dr_templates: Mapped[List["DRTemplate"]] = relationship("DRTemplate", back_populates="organization")


class UserOrganization(Base):
    __tablename__ = "user_organizations"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String, default="member", nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="organizations")
    organization: Mapped["Organization"] = relationship("Organization", back_populates="members")
