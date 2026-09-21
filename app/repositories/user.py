"""Database queries for authenticated users."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """Encapsulate persistence operations for owner accounts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        statement = select(User).where(func.lower(User.email) == email.lower())
        return (await self._session.scalars(statement)).one_or_none()

    async def count_for_business(self, business_id: UUID) -> int:
        statement = select(func.count(User.id)).where(User.business_id == business_id)
        return int((await self._session.scalar(statement)) or 0)

    async def create(self, *, business_id: UUID, email: str, password_hash: str) -> User:
        user = User(
            business_id=business_id,
            email=email.lower(),
            password_hash=password_hash,
        )
        self._session.add(user)
        return user
