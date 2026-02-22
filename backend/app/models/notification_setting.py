from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func, ARRAY, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.config.database import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class NotificationSetting(Base):
    __tablename__ = "notification_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    notify_on_failure: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_on_success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notify_threshold: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    email_addresses: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)
    slack_webhook_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    organization: Mapped[Optional["Organization"]] = relationship("Organization", back_populates="notification_settings")
    user: Mapped[Optional["User"]] = relationship("User", back_populates="notification_settings")
