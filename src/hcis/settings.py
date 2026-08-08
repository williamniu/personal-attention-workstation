from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HCIS_", env_file=".env", extra="ignore")

    home: Path = Path.cwd()
    database_url: str = "postgresql+psycopg://hcis:hcis@127.0.0.1:5432/hcis"
    api_token: str = "local-development-only"
    api_host: str = "127.0.0.1"
    api_port: int = 8080
    dashboard_port: int = 8501
    log_level: str = "INFO"

    @property
    def data_dir(self) -> Path:
        return self.home / "data"


@lru_cache
def get_settings() -> Settings:
    return Settings()

