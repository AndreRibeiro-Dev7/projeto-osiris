"""Use cases related to customers."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateResourceError, ResourceNotFoundError
from app.models.customer import Customer
from app.repositories.business import BusinessRepository
from app.repositories.customer import CustomerRepository
from app.schemas.customer import CustomerCreate


class CustomerService:
    """Coordinate validation and persistence for customers."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._businesses = BusinessRepository(session)
        self._customers = CustomerRepository(session)

    async def create(self, business_id: UUID, payload: CustomerCreate) -> Customer:
        """Register a customer after checking the parent business and phone."""
        if await self._businesses.get_by_id(business_id) is None:
            raise ResourceNotFoundError("Business not found.")
        if await self._customers.get_by_business_and_phone(business_id, payload.phone):
            raise DuplicateResourceError(
                "A customer with this phone already exists in this business."
            )

        customer = await self._customers.create(business_id=business_id, **payload.model_dump())
        try:
            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            raise DuplicateResourceError(
                "A customer with this phone already exists in this business."
            ) from error

        await self._session.refresh(customer)
        return customer

    async def list(self, business_id: UUID) -> list[Customer]:
        """Return business customers after validating the parent exists."""
        if await self._businesses.get_by_id(business_id) is None:
            raise ResourceNotFoundError("Business not found.")
        return await self._customers.list_by_business(business_id)
