from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HCIS_", extra="ignore")

    home: Path = Path.cwd()
    database_url: str = "sqlite:///data/hcis.sqlite3"
    api_token: str = "local-development-only"
    api_host: str = "127.0.0.1"
    api_port: int = 8080
    dashboard_port: int = 8501
    log_level: str = "INFO"

    @property
    def data_dir(self) -> Path:
        return self.home / "data"

    @property
    def database_path(self) -> Path:
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            raise ValueError("HCIS_DATABASE_URL must use sqlite:///")
        path = Path(self.database_url.removeprefix(prefix))
        return path if path.is_absolute() else self.home / path


def load_settings(home: Path | None = None) -> Settings:
    resolved_home = (home or Path(os.environ.get("HCIS_HOME", Path.cwd()))).resolve()
    return Settings(home=resolved_home, _env_file=resolved_home / ".env")  # type: ignore[call-arg]


@lru_cache
def get_settings() -> Settings:
    return load_settings()
