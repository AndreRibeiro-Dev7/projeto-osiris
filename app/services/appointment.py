"""Use cases related to barber appointments."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InactiveBarberError,
    InvalidSchedulingReferenceError,
    ResourceNotFoundError,
    SchedulingConflictError,
)
from app.models.appointment import Appointment
from app.repositories.appointment import AppointmentRepository
from app.repositories.barber import BarberRepository
from app.repositories.business import BusinessRepository
from app.repositories.customer import CustomerRepository
from app.schemas.appointment import AppointmentCreate


class AppointmentService:
    """Coordinate the rules required to reserve a barber's time."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._appointments = AppointmentRepository(session)
        self._barbers = BarberRepository(session)
        self._businesses = BusinessRepository(session)
        self._customers = CustomerRepository(session)

    async def create(self, business_id: UUID, payload: AppointmentCreate) -> Appointment:
        """Create an appointment when all references and the time range are valid."""
        if await self._businesses.get_by_id(business_id) is None:
            raise ResourceNotFoundError("Business not found.")

        barber = await self._barbers.get_by_id_for_update(payload.barber_id)
        if barber is None:
            raise ResourceNotFoundError("Barber not found.")
        if not barber.is_active:
            raise InactiveBarberError("Appointments cannot be made with an inactive barber.")
        if barber.business_id != business_id:
            raise InvalidSchedulingReferenceError("Barber does not belong to this business.")

        customer = await self._customers.get_by_id(payload.customer_id)
        if customer is None:
            raise ResourceNotFoundError("Customer not found.")
        if customer.business_id != business_id:
            raise InvalidSchedulingReferenceError("Customer does not belong to this business.")

        if await self._appointments.has_active_conflict(
            barber_id=barber.id,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
        ):
            raise SchedulingConflictError(
                "The barber already has an appointment in this time range."
            )

        appointment = await self._appointments.create(
            business_id=business_id,
            barber_id=barber.id,
            customer_id=customer.id,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            notes=payload.notes,
        )
        await self._session.commit()
        await self._session.refresh(appointment)
        return appointment
