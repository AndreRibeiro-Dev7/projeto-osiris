"""Use cases related to barbers."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateResourceError, ResourceNotFoundError
from app.models.barber import Barber
from app.repositories.barber import BarberRepository
from app.repositories.business import BusinessRepository
from app.schemas.barber import BarberCreate


class BarberService:
    """Coordinate validation and persistence for barbers."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._barbers = BarberRepository(session)
        self._businesses = BusinessRepository(session)

    async def create(self, business_id: UUID, payload: BarberCreate) -> Barber:
        """Register a barber after checking the parent business and phone."""
        if await self._businesses.get_by_id(business_id) is None:
            raise ResourceNotFoundError("Business not found.")
        if await self._barbers.get_by_business_and_phone(business_id, payload.phone):
            raise DuplicateResourceError(
                "A barber with this phone already exists in this business."
            )

        barber = await self._barbers.create(business_id=business_id, **payload.model_dump())
        try:
            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            raise DuplicateResourceError(
                "A barber with this phone already exists in this business."
            ) from error

        await self._session.refresh(barber)
        return barber

    async def list(self, business_id: UUID) -> list[Barber]:
        """Return business barbers after validating the parent exists."""
        if await self._businesses.get_by_id(business_id) is None:
            raise ResourceNotFoundError("Business not found.")
        return await self._barbers.list_by_business(business_id)
