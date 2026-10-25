"""Tests for environment-driven application settings."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_render_postgres_url_uses_asyncpg_driver() -> None:
    settings = Settings(
        database_url="postgresql://user:password@database.internal:5432/osiris",
    )

    assert (
        settings.database_url == "postgresql+asyncpg://user:password@database.internal:5432/osiris"
    )


def test_legacy_postgres_url_uses_asyncpg_driver() -> None:
    settings = Settings(
        database_url="postgres://user:password@database.internal:5432/osiris",
    )

    assert (
        settings.database_url == "postgresql+asyncpg://user:password@database.internal:5432/osiris"
    )


def test_explicit_async_driver_is_preserved() -> None:
    url = "postgresql+asyncpg://user:password@database.internal:5432/osiris"

    settings = Settings(database_url=url)

    assert settings.database_url == url


def test_log_level_is_normalized() -> None:
    settings = Settings(log_level="warning")

    assert settings.log_level == "WARNING"


def test_invalid_log_level_is_rejected() -> None:
    with pytest.raises(ValidationError, match="LOG_LEVEL"):
        Settings(log_level="verbose")


def test_operational_alert_limits_are_validated() -> None:
    with pytest.raises(ValidationError, match="OPERATIONAL_ALERT_WEBHOOK_URL"):
        Settings(operational_alert_webhook_url="http://alerts.example.test/osiris")

    with pytest.raises(ValidationError, match="OPERATIONAL_ALERT_COOLDOWN_SECONDS"):
        Settings(operational_alert_cooldown_seconds=-1)

    with pytest.raises(ValidationError, match="OPERATIONAL_ALERT_TIMEOUT_SECONDS"):
        Settings(operational_alert_timeout_seconds=0)
