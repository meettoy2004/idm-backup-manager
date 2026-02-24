import os
import logging
from typing import List
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

_DEV_SECRET_KEY = "dev-secret-key-change-in-production"
_DEV_VAULT_TOKEN = "dev-root-token"
_DEV_ADMIN_PASSWORD = "changeme123"

class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = _DEV_SECRET_KEY

    # Database
    DATABASE_URL: str = "postgresql://idm:idm_dev_password@postgres:5432/idm_backup"

    # Redis
    REDIS_URL: str = "redis://:redis_dev_password@redis:6379/0"

    # Vault
    VAULT_ADDR: str = "http://vault:8200"
    VAULT_TOKEN: str = _DEV_VAULT_TOKEN

    # CORS - Allow requests from these origins (comma-separated string, use "*" for all)
    CORS_ORIGINS_STR: str = "*"

    # Bootstrap admin
    BOOTSTRAP_ADMIN_EMAIL: str = "admin@local"
    BOOTSTRAP_ADMIN_PASSWORD: str = _DEV_ADMIN_PASSWORD

    # SMTP for email notifications
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "idm-backup@localhost"
    SMTP_TLS: bool = True

    @property
    def CORS_ORIGINS(self) -> List[str]:
        """Parse CORS_ORIGINS from comma-separated string or wildcard"""
        if self.CORS_ORIGINS_STR == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS_STR.split(",")]

    class Config:
        case_sensitive = True
        env_file = ".env"
        env_prefix = ""


settings = Settings()

# Warn loudly if running with dev defaults outside development
if settings.APP_ENV != "development":
    if settings.SECRET_KEY == _DEV_SECRET_KEY:
        logger.critical("SECRET_KEY is set to the development default — this is INSECURE in production. Set SECRET_KEY env var.")
    if settings.VAULT_TOKEN == _DEV_VAULT_TOKEN:
        logger.critical("VAULT_TOKEN is set to the development default — this is INSECURE in production. Set VAULT_TOKEN env var.")
    if settings.BOOTSTRAP_ADMIN_PASSWORD == _DEV_ADMIN_PASSWORD:
        logger.warning("BOOTSTRAP_ADMIN_PASSWORD is set to the development default. Set BOOTSTRAP_ADMIN_PASSWORD env var.")
    if settings.CORS_ORIGINS_STR == "*":
        logger.warning("CORS_ORIGINS_STR is '*' — restrict this to your frontend domain in production.")
