"""Use cases related to barbershops."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateResourceError, ResourceNotFoundError
from app.models.business import Business
from app.repositories.business import BusinessRepository
from app.schemas.business import BusinessCreate


class BusinessService:
    """Coordinate validation and persistence for businesses."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = BusinessRepository(session)

    async def create(self, payload: BusinessCreate) -> Business:
        """Register a new business with a unique phone."""
        if await self._repository.get_by_phone(payload.phone):
            raise DuplicateResourceError("A business with this phone already exists.")

        business = await self._repository.create(**payload.model_dump())
        try:
            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            raise DuplicateResourceError("A business with this phone already exists.") from error

        await self._session.refresh(business)
        return business

    async def get(self, business_id: UUID) -> Business:
        """Fetch a business or raise an application-level not-found error."""
        business = await self._repository.get_by_id(business_id)
        if business is None:
            raise ResourceNotFoundError("Business not found.")
        return business
