"""Typed application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the application."""

    app_name: str = "Projeto Osiris"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+asyncpg://osiris:osiris@localhost:5432/osiris"
    database_echo: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return a single settings instance for the process."""
    return Settings()
