"""Use cases related to barber appointments."""

from datetime import UTC, date, datetime, time, timedelta
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
from app.models.appointment import Appointment, AppointmentStatus, PaymentMethod
from app.repositories.appointment import AppointmentRepository
from app.repositories.barber import BarberRepository
from app.repositories.business import BusinessRepository
from app.repositories.business_closure import BusinessClosureRepository
from app.repositories.customer import CustomerRepository
from app.repositories.service import ServiceRepository
from app.schemas.appointment import AppointmentCreate, AppointmentRescheduleRequest


class AppointmentService:
    """Coordinate the rules required to reserve a barber's time."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._appointments = AppointmentRepository(session)
        self._barbers = BarberRepository(session)
        self._businesses = BusinessRepository(session)
        self._closures = BusinessClosureRepository(session)
        self._customers = CustomerRepository(session)
        self._services = ServiceRepository(session)

    async def create(self, business_id: UUID, payload: AppointmentCreate) -> Appointment:
        """Create an appointment when all references and the time range are valid."""
        business = await self._businesses.get_by_id(business_id)
        if business is None:
            raise ResourceNotFoundError("Business not found.")
        local_date = payload.starts_at.astimezone(ZoneInfo(business.timezone)).date()
        if await self._closures.get_for_date(business_id, local_date):
            raise SchedulingConflictError("The business is closed on this date.")

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

        service = None
        if payload.service_id is not None:
            service = await self._services.get_by_id(payload.service_id)
            if service is None:
                raise ResourceNotFoundError("Service not found.")
            if service.business_id != business_id:
                raise InvalidSchedulingReferenceError("Service does not belong to this business.")
            if not service.is_active:
                raise InvalidSchedulingReferenceError("Service is inactive.")

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
            service_id=service.id if service else None,
            price_cents=service.price_cents if service else None,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            notes=payload.notes,
        )
        await self._session.commit()
        await self._session.refresh(appointment)
        return appointment

    async def get(self, appointment_id: UUID) -> Appointment:
        """Return one appointment by identifier."""
        appointment = await self._appointments.get_by_id(appointment_id)
        if appointment is None:
            raise ResourceNotFoundError("Appointment not found.")
        return appointment

    async def update_notes(
        self, business_id: UUID, appointment_id: UUID, notes: str | None
    ) -> Appointment:
        """Update operational notes while enforcing business ownership."""
        appointment = await self._appointments.get_by_id_for_update(appointment_id)
        if appointment is None:
            raise ResourceNotFoundError("Appointment not found.")
        if appointment.business_id != business_id:
            raise InvalidSchedulingReferenceError(
                "Appointment does not belong to this business."
            )
        appointment.notes = notes
        await self._session.commit()
        await self._session.refresh(appointment)
        return appointment

    async def reschedule(
        self,
        business_id: UUID,
        appointment_id: UUID,
        payload: AppointmentRescheduleRequest,
    ) -> Appointment:
        """Move an active appointment to another available time."""
        appointment = await self._appointments.get_by_id_for_update(appointment_id)
        if appointment is None:
            raise ResourceNotFoundError("Appointment not found.")
        if appointment.business_id != business_id:
            raise InvalidSchedulingReferenceError("Appointment does not belong to this business.")
        if appointment.status not in {AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED}:
            raise InvalidAppointmentStatusTransitionError(
                f"Cannot reschedule an appointment with status {appointment.status.value}."
            )
        barber = await self._barbers.get_by_id(payload.barber_id)
        if barber is None or barber.business_id != business_id:
            raise InvalidSchedulingReferenceError("Barber does not belong to this business.")
        if not barber.is_active:
            raise InactiveBarberError("Appointments cannot be made with an inactive barber.")
        service = await self._services.get_by_id(payload.service_id)
        if service is None or service.business_id != business_id or not service.is_active:
            raise InvalidSchedulingReferenceError("Service is not available for this business.")
        ends_at = payload.starts_at + timedelta(minutes=service.duration_minutes)
        if await self._appointments.has_active_conflict(
            barber_id=barber.id,
            starts_at=payload.starts_at,
            ends_at=ends_at,
            exclude_appointment_id=appointment.id,
        ):
            raise SchedulingConflictError("The barber already has an appointment in this time range.")
        appointment.barber_id = barber.id
        appointment.service_id = service.id
        appointment.price_cents = service.price_cents
        appointment.starts_at = payload.starts_at
        appointment.ends_at = ends_at
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
        return await self._appointments.list_for_barber(
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

    async def complete(
        self, business_id: UUID, appointment_id: UUID, payment_method: PaymentMethod
    ) -> Appointment:
        """Complete an appointment and record its payment."""
        appointment = await self._change_status(
            business_id=business_id,
            appointment_id=appointment_id,
            expected_statuses={AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED},
            new_status=AppointmentStatus.COMPLETED,
            commit=False,
        )
        appointment.payment_method = payment_method
        appointment.paid_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(appointment)
        return appointment

    async def mark_no_show(self, business_id: UUID, appointment_id: UUID) -> Appointment:
        """Mark an active appointment when the customer did not attend."""
        return await self._change_status(
            business_id=business_id,
            appointment_id=appointment_id,
            expected_statuses={AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED},
            new_status=AppointmentStatus.NO_SHOW,
        )

    async def _change_status(
        self,
        *,
        business_id: UUID,
        appointment_id: UUID,
        expected_statuses: set[AppointmentStatus],
        new_status: AppointmentStatus,
        commit: bool = True,
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
        if commit:
            await self._session.commit()
            await self._session.refresh(appointment)
        return appointment
