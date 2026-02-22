from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..config.database import Base

class BackupJob(Base):
    __tablename__ = "backup_jobs"

    id            = Column(Integer, primary_key=True, index=True)
    server_id     = Column(Integer, ForeignKey("servers.id"), nullable=False)
    config_id     = Column(Integer, ForeignKey("backup_configs.id"), nullable=True)
    status        = Column(String, nullable=False)  # SUCCESS, FAILED, RUNNING, PENDING
    started_at    = Column(DateTime(timezone=True), nullable=True)
    completed_at  = Column(DateTime(timezone=True), nullable=True)
    log_output    = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships - use string references to avoid circular imports
    server = relationship("Server", back_populates="backup_jobs")
    config = relationship("BackupConfig", back_populates="backup_jobs")
