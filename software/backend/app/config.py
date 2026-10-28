from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ALLOWED = frozenset({"debug", "info", "warning", "error", "critical", "none"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    app_version: str = Field(default="0.1.5", validation_alias="APP_VERSION")
    log_level: str = Field(default="info", validation_alias="LOG_LEVEL")
    data_dir: str = Field(default="/data/app", validation_alias="DATA_DIR")
    api_token: str = Field(default="", validation_alias="API_TOKEN")
    dry_run: bool = Field(default=True, validation_alias="DRY_RUN")
    interval_seconds: int = Field(default=900, validation_alias="INTERVAL_SECONDS")
    cluster_ids: str = Field(
        default="cluster-a,cluster-b",
        validation_alias="CLUSTER_IDS",
    )
    argocd_namespace: str = Field(default="argocd", validation_alias="ARGOCD_NAMESPACE")

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize(cls, value: object) -> str:
        normalized = str(value or "info").strip().lower()
        return normalized if normalized in _ALLOWED else "info"

    @field_validator("dry_run", mode="before")
    @classmethod
    def as_bool(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"1", "true", "yes", "si"}

    @property
    def clusters(self) -> list[str]:
        return [item.strip() for item in self.cluster_ids.split(",") if item.strip()]


settings = Settings()
