"""Database queries for customers."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer


class CustomerRepository:
    """Encapsulate persistence operations for customers."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, customer_id: UUID) -> Customer | None:
        """Return a customer by primary key when it exists."""
        return await self._session.get(Customer, customer_id)

    async def get_by_business_and_phone(self, business_id: UUID, phone: str) -> Customer | None:
        """Return a customer by their business-scoped phone."""
        statement = select(Customer).where(
            Customer.business_id == business_id, Customer.phone == phone
        )
        result = await self._session.scalars(statement)
        return result.one_or_none()

    async def list_by_business(self, business_id: UUID) -> list[Customer]:
        """Return customers belonging to a business."""
        statement = (
            select(Customer).where(Customer.business_id == business_id).order_by(Customer.full_name)
        )
        return list((await self._session.scalars(statement)).all())

    async def create(self, *, business_id: UUID, full_name: str, phone: str) -> Customer:
        """Add a new customer to the current unit of work."""
        customer = Customer(business_id=business_id, full_name=full_name, phone=phone)
        self._session.add(customer)
        return customer
