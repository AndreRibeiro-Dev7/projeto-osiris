"""Use cases related to barbershops."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateResourceError, ResourceNotFoundError
from app.models.business import Business
from app.repositories.business import BusinessRepository
from app.schemas.business import BusinessCreate, BusinessUpdate

BUSINESS_PHONE_ALREADY_EXISTS = "Já existe uma empresa cadastrada com este telefone."


class BusinessService:
    """Coordinate validation and persistence for businesses."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = BusinessRepository(session)

    async def create(self, payload: BusinessCreate) -> Business:
        """Register a new business with a unique phone."""
        if await self._repository.get_by_phone(payload.phone):
            raise DuplicateResourceError(BUSINESS_PHONE_ALREADY_EXISTS)

        business = await self._repository.create(**payload.model_dump())
        try:
            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            raise DuplicateResourceError(BUSINESS_PHONE_ALREADY_EXISTS) from error

        await self._session.refresh(business)
        return business

    async def get(self, business_id: UUID) -> Business:
        """Fetch a business or raise an application-level not-found error."""
        business = await self._repository.get_by_id(business_id)
        if business is None:
            raise ResourceNotFoundError("Business not found.")
        return business

    async def update(self, business_id: UUID, payload: BusinessUpdate) -> Business:
        """Update a barbershop profile while keeping its phone unique."""
        business = await self.get(business_id)
        phone_owner = await self._repository.get_by_phone(payload.phone)
        if phone_owner is not None and phone_owner.id != business.id:
            raise DuplicateResourceError(BUSINESS_PHONE_ALREADY_EXISTS)

        business.name = payload.name
        business.phone = payload.phone
        business.timezone = payload.timezone
        business.loyalty_enabled = payload.loyalty_enabled
        business.loyalty_target = payload.loyalty_target
        business.loyalty_reward = payload.loyalty_reward
        business.monthly_revenue_goal_cents = payload.monthly_revenue_goal_cents
        try:
            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            raise DuplicateResourceError(BUSINESS_PHONE_ALREADY_EXISTS) from error
        await self._session.refresh(business)
        return business
