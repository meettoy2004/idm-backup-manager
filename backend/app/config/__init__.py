from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    APP_NAME:   str  = "IDM Backup Manager"
    APP_ENV:    str  = "development"
    DEBUG:      bool = True
    SECRET_KEY: str  = "change-this-in-production"

    DATABASE_URL:   str
    VAULT_ADDR:     str = "http://127.0.0.1:8200"
    VAULT_TOKEN:    str = "dev-root-token"
    VAULT_SSH_PATH: str = "secret/ssh/service-account"
    VAULT_DB_PATH:  str = "secret/database"
    REDIS_URL:      str = "redis://localhost:6379/0"
    API_V1_PREFIX:  str = "/api/v1"

    SSH_CONNECTION_TIMEOUT: int = 30
    SSH_COMMAND_TIMEOUT:    int = 300

    CORS_ORIGINS: List[str] = ["http://localhost:5173","http://localhost:5174","http://localhost:3000"]

    FRONTEND_URL:             str = "http://localhost:5174"
    BOOTSTRAP_ADMIN_EMAIL:    str = "admin@local"
    BOOTSTRAP_ADMIN_PASSWORD: str = "changeme123"

    # OIDC — all optional
    OIDC_GOOGLE_CLIENT_ID:     str = ""
    OIDC_GOOGLE_CLIENT_SECRET: str = ""
    OIDC_AZURE_CLIENT_ID:      str = ""
    OIDC_AZURE_CLIENT_SECRET:  str = ""
    OIDC_AZURE_TENANT_ID:      str = "common"
    OIDC_CUSTOM_CLIENT_ID:     str = ""
    OIDC_CUSTOM_CLIENT_SECRET: str = ""
    OIDC_CUSTOM_AUTH_URL:      str = ""
    OIDC_CUSTOM_TOKEN_URL:     str = ""
    OIDC_CUSTOM_USERINFO_URL:  str = ""
    OIDC_CUSTOM_LABEL:         str = "SSO"

    class Config:
        env_file = ".env"
        extra   = "ignore"    # ignore any extra fields in .env

settings = Settings()
