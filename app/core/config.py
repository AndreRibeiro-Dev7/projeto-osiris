"""Typed application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration for the application."""

    app_name: str = "Projeto Osiris"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    log_json: bool = False
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
    discord_alert_webhook_url: str = ""
    operational_alert_cooldown_seconds: int = 300
    operational_alert_timeout_seconds: float = 5.0

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

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        """Accept only standard Python logging levels."""
        if isinstance(value, str):
            normalized = value.upper()
            if normalized in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
                return normalized
        raise ValueError("LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL.")

    @field_validator("discord_alert_webhook_url")
    @classmethod
    def validate_discord_alert_webhook_url(cls, value: str) -> str:
        """Accept only official encrypted Discord webhook endpoints."""
        if not value:
            return value
        parsed = urlparse(value)
        allowed_hosts = {"discord.com", "www.discord.com", "discordapp.com"}
        if (
            parsed.scheme != "https"
            or parsed.hostname not in allowed_hosts
            or not parsed.path.startswith("/api/webhooks/")
        ):
            raise ValueError("DISCORD_ALERT_WEBHOOK_URL must be an official Discord webhook URL.")
        return value

    @field_validator("operational_alert_cooldown_seconds")
    @classmethod
    def validate_alert_cooldown(cls, value: int) -> int:
        """Allow disabling deduplication while rejecting negative cooldowns."""
        if value < 0:
            raise ValueError("OPERATIONAL_ALERT_COOLDOWN_SECONDS cannot be negative.")
        return value

    @field_validator("operational_alert_timeout_seconds")
    @classmethod
    def validate_alert_timeout(cls, value: float) -> float:
        """Keep webhook failures from delaying API responses for too long."""
        if not 0 < value <= 30:
            raise ValueError("OPERATIONAL_ALERT_TIMEOUT_SECONDS must be between 0 and 30.")
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
