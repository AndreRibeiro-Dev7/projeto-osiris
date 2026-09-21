"""Tests for environment-driven application settings."""

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
