"""Use cases for barber working hours and free time slots."""

from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InactiveBarberError,
    InvalidSchedulingReferenceError,
    ResourceNotFoundError,
)
from app.models.barber_schedule import BarberSchedule
from app.repositories.appointment import AppointmentRepository
from app.repositories.barber import BarberRepository
from app.repositories.barber_schedule import BarberScheduleRepository
from app.repositories.business import BusinessRepository
from app.schemas.availability import (
    AvailabilityResponse,
    AvailabilitySlot,
    BarberScheduleUpsert,
)


class AvailabilityService:
    """Configure recurring work and calculate appointment availability."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._appointments = AppointmentRepository(session)
        self._barbers = BarberRepository(session)
        self._businesses = BusinessRepository(session)
        self._schedules = BarberScheduleRepository(session)

    async def upsert_schedule(
        self,
        *,
        business_id: UUID,
        barber_id: UUID,
        weekday: int,
        payload: BarberScheduleUpsert,
    ) -> BarberSchedule:
        """Create or replace a barber's recurring schedule for one weekday."""
        await self._validate_barber(business_id, barber_id, require_active=False)
        schedule = await self._schedules.upsert(
            barber_id=barber_id,
            weekday=weekday,
            payload=payload,
        )
        await self._session.commit()
        await self._session.refresh(schedule)
        return schedule

    async def list_available_slots(
        self,
        *,
        business_id: UUID,
        barber_id: UUID,
        appointment_date: date,
    ) -> AvailabilityResponse:
        """Return free slots inside the configured local working window."""
        business = await self._businesses.get_by_id(business_id)
        if business is None:
            raise ResourceNotFoundError("Business not found.")
        await self._validate_barber(business_id, barber_id, require_active=True)

        schedule = await self._schedules.get(barber_id, appointment_date.weekday())
        if schedule is None:
            return AvailabilityResponse(
                business_id=business_id,
                barber_id=barber_id,
                appointment_date=appointment_date,
                timezone=business.timezone,
                slots=[],
            )

        timezone = ZoneInfo(business.timezone)
        work_starts_at = datetime.combine(appointment_date, schedule.starts_at, tzinfo=timezone)
        work_ends_at = datetime.combine(appointment_date, schedule.ends_at, tzinfo=timezone)
        appointments = await self._appointments.list_active_overlapping(
            barber_id=barber_id,
            starts_at=work_starts_at,
            ends_at=work_ends_at,
        )

        slot_length = timedelta(minutes=schedule.slot_duration_minutes)
        slots: list[AvailabilitySlot] = []
        starts_at = work_starts_at
        while starts_at + slot_length <= work_ends_at:
            ends_at = starts_at + slot_length
            if not any(
                appointment.starts_at < ends_at and appointment.ends_at > starts_at
                for appointment in appointments
            ):
                slots.append(AvailabilitySlot(starts_at=starts_at, ends_at=ends_at))
            starts_at = ends_at

        return AvailabilityResponse(
            business_id=business_id,
            barber_id=barber_id,
            appointment_date=appointment_date,
            timezone=business.timezone,
            slots=slots,
        )

    async def _validate_barber(
        self, business_id: UUID, barber_id: UUID, *, require_active: bool
    ) -> None:
        """Ensure the barber exists and belongs to the requested business."""
        barber = await self._barbers.get_by_id(barber_id)
        if barber is None:
            raise ResourceNotFoundError("Barber not found.")
        if barber.business_id != business_id:
            raise InvalidSchedulingReferenceError("Barber does not belong to this business.")
        if require_active and not barber.is_active:
            raise InactiveBarberError("Availability is not offered for an inactive barber.")
