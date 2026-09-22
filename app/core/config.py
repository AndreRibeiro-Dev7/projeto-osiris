"""Typed application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration for the application."""

    app_name: str = "Projeto Osiris"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+asyncpg://osiris:osiris@localhost:5432/osiris"
    database_echo: bool = False
    openai_api_key: str = ""
    openai_model: str = "gpt-5.6-luna"
    jwt_secret_key: str = ""
    owner_bootstrap_enabled: bool = False
    owner_bootstrap_token: str = ""
    access_token_expire_minutes: int = 60
    resend_api_key: str = ""
    resend_from_email: str = "Osiris <onboarding@resend.dev>"
    email_delivery_enabled: bool = False

    @field_validator("database_url", mode="before")
    @classmethod
    def use_async_postgres_driver(cls, value: object) -> object:
        """Use asyncpg for generic PostgreSQL URLs supplied by hosting providers."""
        if isinstance(value, str):
            if value.startswith("postgres://"):
                return value.replace("postgres://", "postgresql+asyncpg://", 1)
            if value.startswith("postgresql://"):
                return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a single settings instance for the process."""
    return Settings()
