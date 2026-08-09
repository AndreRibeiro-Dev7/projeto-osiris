"""Database queries for barbers."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.barber import Barber


class BarberRepository:
    """Encapsulate persistence operations for barbers."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_business_and_phone(self, business_id: UUID, phone: str) -> Barber | None:
        """Return a barber by their business-scoped phone."""
        statement = select(Barber).where(Barber.business_id == business_id, Barber.phone == phone)
        result = await self._session.scalars(statement)
        return result.one_or_none()

    async def list_by_business(self, business_id: UUID) -> list[Barber]:
        """Return the active and inactive professionals of a business."""
        statement = (
            select(Barber).where(Barber.business_id == business_id).order_by(Barber.full_name)
        )
        return list((await self._session.scalars(statement)).all())

    async def create(self, *, business_id: UUID, full_name: str, phone: str) -> Barber:
        """Add a new barber to the current unit of work."""
        barber = Barber(business_id=business_id, full_name=full_name, phone=phone)
        self._session.add(barber)
        return barber
