"""Async SQLAlchemy engine and session lifecycle."""

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,
)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide one database session per request and close it afterwards."""
    async with async_session_factory() as session:
        yield session


async def is_database_available(session: AsyncSession) -> bool:
    """Return whether the current session can execute a minimal query."""
    await session.execute(text("SELECT 1"))
    return True
