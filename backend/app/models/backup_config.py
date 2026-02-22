from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..config.database import Base

class BackupConfig(Base):
    __tablename__ = "backup_configs"

    id              = Column(Integer, primary_key=True, index=True)
    server_id       = Column(Integer, ForeignKey("servers.id"), nullable=False)
    schedule        = Column(String, nullable=False)
    retention_count = Column(Integer, default=10)
    s3_mount_dir    = Column(String, nullable=False)
    backup_dir      = Column(String, default="/var/lib/ipa/backup")
    is_enabled      = Column(Boolean, default=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    # Phase 1: Multi-tenancy
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)

    # Relationships
    server       = relationship("Server", back_populates="backup_configs")
    backup_jobs  = relationship("BackupJob", back_populates="config")
    organization = relationship("Organization", back_populates="backup_configs")
