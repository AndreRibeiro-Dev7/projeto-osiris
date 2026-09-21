"""Use cases related to customers."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DuplicateResourceError,
    LoyaltyRewardUnavailableError,
    ResourceNotFoundError,
)
from app.models.customer import Customer
from app.models.appointment import Appointment, AppointmentStatus
from app.repositories.appointment import AppointmentRepository
from app.repositories.business import BusinessRepository
from app.repositories.customer import CustomerRepository
from app.schemas.customer import CustomerCreate, CustomerPortfolioEntry, CustomerUpdate


class CustomerService:
    """Coordinate validation and persistence for customers."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._businesses = BusinessRepository(session)
        self._customers = CustomerRepository(session)
        self._appointments = AppointmentRepository(session)

    async def create(self, business_id: UUID, payload: CustomerCreate) -> Customer:
        """Register a customer after checking the parent business and phone."""
        business = await self._businesses.get_by_id(business_id)
        if business is None:
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

    async def update(
        self, business_id: UUID, customer_id: UUID, payload: CustomerUpdate
    ) -> Customer:
        """Update a customer while preserving business-scoped phone uniqueness."""
        customer = await self._customers.get_by_id(customer_id)
        if customer is None or customer.business_id != business_id:
            raise ResourceNotFoundError("Customer not found.")

        phone_owner = await self._customers.get_by_business_and_phone(
            business_id, payload.phone
        )
        if phone_owner is not None and phone_owner.id != customer.id:
            raise DuplicateResourceError(
                "A customer with this phone already exists in this business."
            )

        customer.full_name = payload.full_name
        customer.phone = payload.phone
        customer.notes = payload.notes
        customer.birth_date = payload.birth_date
        try:
            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            raise DuplicateResourceError(
                "A customer with this phone already exists in this business."
            ) from error

        await self._session.refresh(customer)
        return customer

    async def appointment_history(
        self, business_id: UUID, customer_id: UUID
    ) -> list[Appointment]:
        """Return appointments for a customer belonging to the business."""
        customer = await self._customers.get_by_id(customer_id)
        if customer is None or customer.business_id != business_id:
            raise ResourceNotFoundError("Customer not found.")
        return await self._appointments.list_by_customer(customer_id)

    async def portfolio(self, business_id: UUID) -> list[CustomerPortfolioEntry]:
        """Build portfolio metrics for every customer in a business."""
        business = await self._businesses.get_by_id(business_id)
        if business is None:
            raise ResourceNotFoundError("Business not found.")

        customers = await self._customers.list_by_business(business_id)
        appointments = await self._appointments.list_by_business(business_id)
        by_customer: dict[UUID, list[Appointment]] = {}
        for appointment in appointments:
            by_customer.setdefault(appointment.customer_id, []).append(appointment)

        rows: list[CustomerPortfolioEntry] = []
        for customer in customers:
            history = by_customer.get(customer.id, [])
            completed = [
                item for item in history if item.status == AppointmentStatus.COMPLETED
            ]
            rows.append(
                CustomerPortfolioEntry(
                    id=customer.id,
                    full_name=customer.full_name,
                    phone=customer.phone,
                    created_at=customer.created_at,
                    appointments=len(history),
                    completed=len(completed),
                    no_show=sum(
                        item.status == AppointmentStatus.NO_SHOW for item in history
                    ),
                    total_spent_cents=sum(item.price_cents or 0 for item in completed),
                    last_visit_at=max(
                        (item.starts_at for item in completed), default=None
                    ),
                    loyalty_enabled=business.loyalty_enabled,
                    loyalty_progress=len(completed) % business.loyalty_target,
                    loyalty_target=business.loyalty_target,
                    loyalty_rewards=len(completed) // business.loyalty_target,
                    loyalty_rewards_redeemed=customer.loyalty_rewards_redeemed,
                    loyalty_rewards_available=max(
                        0,
                        len(completed) // business.loyalty_target
                        - customer.loyalty_rewards_redeemed,
                    ),
                    loyalty_reward=business.loyalty_reward,
                )
            )
        return rows

    async def redeem_loyalty_reward(
        self, business_id: UUID, customer_id: UUID
    ) -> None:
        """Consume one earned loyalty reward for a customer."""
        business = await self._businesses.get_by_id(business_id)
        customer = await self._customers.get_by_id_for_update(customer_id)
        if business is None or customer is None or customer.business_id != business_id:
            raise ResourceNotFoundError("Customer not found.")
        if not business.loyalty_enabled:
            raise LoyaltyRewardUnavailableError("The loyalty program is disabled.")

        history = await self._appointments.list_by_customer(customer_id)
        completed = sum(
            item.status == AppointmentStatus.COMPLETED for item in history
        )
        earned = completed // business.loyalty_target
        if earned <= customer.loyalty_rewards_redeemed:
            raise LoyaltyRewardUnavailableError(
                "This customer has no loyalty reward available."
            )

        customer.loyalty_rewards_redeemed += 1
        await self._session.commit()
