"""Database queries for appointments."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment, AppointmentStatus


class AppointmentRepository:
    """Encapsulate persistence operations for appointments."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def has_active_conflict(
        self,
        *,
        barber_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
    ) -> bool:
        """Return whether an active appointment overlaps the requested time range."""
        statement = (
            select(Appointment.id)
            .where(
                Appointment.barber_id == barber_id,
                Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED]),
                Appointment.starts_at < ends_at,
                Appointment.ends_at > starts_at,
            )
            .limit(1)
        )
        result = await self._session.scalars(statement)
        return result.first() is not None

    async def create(
        self,
        *,
        business_id: UUID,
        barber_id: UUID,
        customer_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
        notes: str | None,
    ) -> Appointment:
        """Add a scheduled appointment to the current unit of work."""
        appointment = Appointment(
            business_id=business_id,
            barber_id=barber_id,
            customer_id=customer_id,
            starts_at=starts_at,
            ends_at=ends_at,
            notes=notes,
        )
        self._session.add(appointment)
        return appointment
