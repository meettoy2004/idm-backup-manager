from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON
from sqlalchemy.sql import func
from ..config.database import Base

class AuthProvider(Base):
    __tablename__ = "auth_providers"

    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String, nullable=False)          # "Keycloak", "Company LDAP"
    type       = Column(String, nullable=False, index=True)  # oidc / ldap / saml
    is_enabled = Column(Boolean, default=True)
    config     = Column(JSON, nullable=False, default={})    # provider-specific config
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
