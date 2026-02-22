from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.config.database import Base

if TYPE_CHECKING:
    from app.models.backup_job import BackupJob


class VerificationLog(Base):
    __tablename__ = "verification_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("backup_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    verification_status: Mapped[str] = mapped_column(String, nullable=False, default="PENDING")
    gpg_verify_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    integrity_check_passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    job: Mapped["BackupJob"] = relationship("BackupJob", back_populates="verification_logs")
