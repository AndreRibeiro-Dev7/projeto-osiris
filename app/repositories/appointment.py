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

    async def get_by_id(self, appointment_id: UUID) -> Appointment | None:
        """Return one appointment without acquiring a row lock."""
        return await self._session.get(Appointment, appointment_id)

    async def get_by_public_token(self, public_token: UUID) -> Appointment | None:
        """Return an appointment using its customer-facing secure token."""
        result = await self._session.scalars(
            select(Appointment).where(Appointment.public_token == public_token)
        )
        return result.one_or_none()

    async def get_by_id_for_update(self, appointment_id: UUID) -> Appointment | None:
        """Return and lock an appointment while changing its status."""
        statement = select(Appointment).where(Appointment.id == appointment_id).with_for_update()
        result = await self._session.scalars(statement)
        return result.one_or_none()

    async def list_for_barber(
        self,
        *,
        barber_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
    ) -> list[Appointment]:
        """Return appointments that start inside a requested time range."""
        statement = (
            select(Appointment)
            .where(
                Appointment.barber_id == barber_id,
                Appointment.starts_at >= starts_at,
                Appointment.starts_at < ends_at,
            )
            .order_by(Appointment.starts_at)
        )
        return list((await self._session.scalars(statement)).all())

    async def list_active_overlapping(
        self,
        *,
        barber_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
    ) -> list[Appointment]:
        """Return active appointments that overlap a requested time range."""
        statement = (
            select(Appointment)
            .where(
                Appointment.barber_id == barber_id,
                Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED]),
                Appointment.starts_at < ends_at,
                Appointment.ends_at > starts_at,
            )
            .order_by(Appointment.starts_at)
        )
        return list((await self._session.scalars(statement)).all())

    async def list_by_business_range(
        self, *, business_id: UUID, starts_at: datetime, ends_at: datetime
    ) -> list[Appointment]:
        """Return all appointments for a business inside a date range."""
        statement = (
            select(Appointment)
            .where(
                Appointment.business_id == business_id,
                Appointment.starts_at >= starts_at,
                Appointment.starts_at < ends_at,
            )
            .order_by(Appointment.starts_at)
        )
        return list((await self._session.scalars(statement)).all())

    async def list_by_customer(self, customer_id: UUID) -> list[Appointment]:
        """Return a customer's complete appointment history, newest first."""
        statement = (
            select(Appointment)
            .where(Appointment.customer_id == customer_id)
            .order_by(Appointment.starts_at.desc())
        )
        return list((await self._session.scalars(statement)).all())

    async def list_by_business(self, business_id: UUID) -> list[Appointment]:
        """Return the complete appointment history for a business."""
        statement = (
            select(Appointment)
            .where(Appointment.business_id == business_id)
            .order_by(Appointment.starts_at.desc())
        )
        return list((await self._session.scalars(statement)).all())

    async def has_active_conflict(
        self,
        *,
        barber_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
        exclude_appointment_id: UUID | None = None,
    ) -> bool:
        """Return whether an active appointment overlaps the requested time range."""
        statement = select(Appointment.id).where(
                Appointment.barber_id == barber_id,
                Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED]),
                Appointment.starts_at < ends_at,
                Appointment.ends_at > starts_at,
        )
        if exclude_appointment_id is not None:
            statement = statement.where(Appointment.id != exclude_appointment_id)
        statement = statement.limit(1)
        result = await self._session.scalars(statement)
        return result.first() is not None

    async def create(
        self,
        *,
        business_id: UUID,
        barber_id: UUID,
        customer_id: UUID,
        service_id: UUID | None,
        price_cents: int | None,
        starts_at: datetime,
        ends_at: datetime,
        notes: str | None,
    ) -> Appointment:
        """Add a scheduled appointment to the current unit of work."""
        appointment = Appointment(
            business_id=business_id,
            barber_id=barber_id,
            customer_id=customer_id,
            service_id=service_id,
            price_cents=price_cents,
            starts_at=starts_at,
            ends_at=ends_at,
            notes=notes,
        )
        self._session.add(appointment)
        return appointment
