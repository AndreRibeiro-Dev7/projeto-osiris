"""Use cases related to barber appointments."""

from datetime import date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InactiveBarberError,
    InvalidAppointmentStatusTransitionError,
    InvalidSchedulingReferenceError,
    ResourceNotFoundError,
    SchedulingConflictError,
)
from app.models.appointment import Appointment, AppointmentStatus
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

    async def list_for_barber(
        self,
        *,
        business_id: UUID,
        barber_id: UUID,
        appointment_date: date,
    ) -> list[Appointment]:
        """Return a barber's active appointments for one local business day."""
        business = await self._businesses.get_by_id(business_id)
        if business is None:
            raise ResourceNotFoundError("Business not found.")

        barber = await self._barbers.get_by_id(barber_id)
        if barber is None:
            raise ResourceNotFoundError("Barber not found.")
        if barber.business_id != business_id:
            raise InvalidSchedulingReferenceError("Barber does not belong to this business.")

        timezone = ZoneInfo(business.timezone)
        starts_at = datetime.combine(appointment_date, time.min, tzinfo=timezone)
        ends_at = starts_at + timedelta(days=1)
        return await self._appointments.list_active_for_barber(
            barber_id=barber_id,
            starts_at=starts_at,
            ends_at=ends_at,
        )

    async def confirm(self, business_id: UUID, appointment_id: UUID) -> Appointment:
        """Confirm an appointment that is waiting for confirmation."""
        return await self._change_status(
            business_id=business_id,
            appointment_id=appointment_id,
            expected_statuses={AppointmentStatus.SCHEDULED},
            new_status=AppointmentStatus.CONFIRMED,
        )

    async def cancel(self, business_id: UUID, appointment_id: UUID) -> Appointment:
        """Cancel an appointment that is still active."""
        return await self._change_status(
            business_id=business_id,
            appointment_id=appointment_id,
            expected_statuses={AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED},
            new_status=AppointmentStatus.CANCELLED,
        )

    async def _change_status(
        self,
        *,
        business_id: UUID,
        appointment_id: UUID,
        expected_statuses: set[AppointmentStatus],
        new_status: AppointmentStatus,
    ) -> Appointment:
        """Change status only when the appointment belongs to the business and is eligible."""
        appointment = await self._appointments.get_by_id_for_update(appointment_id)
        if appointment is None:
            raise ResourceNotFoundError("Appointment not found.")
        if appointment.business_id != business_id:
            raise InvalidSchedulingReferenceError("Appointment does not belong to this business.")
        if appointment.status not in expected_statuses:
            raise InvalidAppointmentStatusTransitionError(
                f"Cannot change an appointment from {appointment.status} to {new_status}."
            )

        appointment.status = new_status
        await self._session.commit()
        await self._session.refresh(appointment)
        return appointment
