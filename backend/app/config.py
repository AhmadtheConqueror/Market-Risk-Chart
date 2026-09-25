from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    app_name: str = "Daily Oil Trading Risk Dashboard API"
    environment: str = "development"
    database_url: str | None = None
    frontend_origin: str = "http://localhost:3000"

    ai_provider: str = "gemini"
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.8-flash"
    ai_timeout_seconds: float = 45.0

    market_data_provider: str = "oilpriceapi"
    oilpriceapi_key: str | None = None
    market_data_api_key: str | None = None
    market_data_base_url: str | None = None

    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("frontend_origin")
    @classmethod
    def reject_wildcard_origin(cls, value: str) -> str:
        origin = value.strip().rstrip("/")
        if not origin or origin == "*":
            raise ValueError("FRONTEND_ORIGIN must be one explicit origin, not '*'.")
        return origin

    @property
    def sqlalchemy_database_url(self) -> str | None:
        if not self.database_url:
            return None

        url = self.database_url.strip()
        if url.startswith("postgres://"):
            return "postgresql+psycopg://" + url.removeprefix("postgres://")
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url.removeprefix("postgresql://")
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
