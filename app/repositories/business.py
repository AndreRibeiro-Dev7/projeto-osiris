"""Database queries for businesses."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business


class BusinessRepository:
    """Encapsulate persistence operations for barbershops."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, business_id: UUID) -> Business | None:
        """Return a business by primary key when it exists."""
        return await self._session.get(Business, business_id)

    async def get_by_phone(self, phone: str) -> Business | None:
        """Return a business by its globally unique phone."""
        statement = select(Business).where(Business.phone == phone)
        result = await self._session.scalars(statement)
        return result.one_or_none()

    async def create(self, *, name: str, phone: str, timezone: str) -> Business:
        """Add a new business to the current unit of work."""
        business = Business(name=name, phone=phone, timezone=timezone)
        self._session.add(business)
        return business
