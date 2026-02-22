import os
from typing import List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    
    # Database
    DATABASE_URL: str = "postgresql://idm:idm_dev_password@postgres:5432/idm_backup"
    
    # Redis
    REDIS_URL: str = "redis://:redis_dev_password@redis:6379/0"
    
    # Vault
    VAULT_ADDR: str = "http://vault:8200"
    VAULT_TOKEN: str = "dev-root-token"
    
    # CORS - Allow requests from these origins (comma-separated string, use "*" for all)
    CORS_ORIGINS_STR: str = "*"
    
    # Bootstrap admin
    BOOTSTRAP_ADMIN_EMAIL: str = "admin@local"
    BOOTSTRAP_ADMIN_PASSWORD: str = "changeme123"
    
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
