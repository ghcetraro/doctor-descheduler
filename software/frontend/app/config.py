from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ALLOWED_LOG_LEVELS = frozenset({"debug", "info", "warning", "error", "critical", "none"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = Field(default="Doctor Descheduler", validation_alias="APP_NAME")
    app_slug: str = Field(default="doctor-descheduler", validation_alias="APP_SLUG")
    app_version: str = Field(default="0.1.5", validation_alias="APP_VERSION")
    data_dir: Path = Field(default=Path("/data/app"), validation_alias="DATA_DIR")
    log_level: str = Field(default="info", validation_alias="LOG_LEVEL")
    backend_url: str = Field(default="http://127.0.0.1:8000", validation_alias="BACKEND_URL")
    api_token: str = Field(default="", validation_alias="API_TOKEN")
    local_auth: bool = Field(default=True, validation_alias="LOCAL_AUTH_ENABLED")
    service_user: str = Field(default="admin", validation_alias="SERVICE_USER")
    service_password: str = Field(default="change-me", validation_alias="SERVICE_PASSWORD")
    oidc_enabled: bool = Field(default=False, validation_alias="OIDC_ENABLED")
    oidc_issuer: str = Field(default="", validation_alias="OIDC_ISSUER")
    oidc_client_id: str = Field(default="doctor-descheduler", validation_alias="OIDC_CLIENT_ID")
    oidc_client_secret: str = Field(default="", validation_alias="OIDC_CLIENT_SECRET")
    oidc_redirect_uri: str = Field(default="", validation_alias="OIDC_REDIRECT_URI")
    oidc_scopes: str = Field(default="openid email profile groups", validation_alias="OIDC_SCOPES")
    oidc_admin_groups: str = Field(default="descheduler-admins", validation_alias="OIDC_ADMIN_GROUPS")
    session_secret: str = Field(default="change-me-session", validation_alias="SESSION_SECRET")
    session_https_only: bool = Field(default=False, validation_alias="SECURE_COOKIES")

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> str:
        normalized = str(value or "info").strip().lower()
        if normalized not in _ALLOWED_LOG_LEVELS:
            return "info"
        return normalized


settings = Settings()
