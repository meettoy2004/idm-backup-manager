from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.config.database import Base

if TYPE_CHECKING:
    from app.models.backup_job import BackupJob
    from app.models.server import Server
    from app.models.user import User


class RestoreOperation(Base):
    __tablename__ = "restore_operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("backup_jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    server_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("servers.id", ondelete="SET NULL"), nullable=True, index=True)
    requested_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    restore_status: Mapped[str] = mapped_column(String, default="pending", nullable=False, index=True)
    restore_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    gpg_decrypt_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    job: Mapped[Optional["BackupJob"]] = relationship("BackupJob", back_populates="restore_operations")
    server: Mapped[Optional["Server"]] = relationship("Server", back_populates="restore_operations")
    requester: Mapped[Optional["User"]] = relationship("User", back_populates="restore_operations")
