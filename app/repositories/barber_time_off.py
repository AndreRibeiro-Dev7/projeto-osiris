"""Persistence for exceptional barber absences."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.barber_time_off import BarberTimeOff


class BarberTimeOffRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, barber_id: UUID, starts_at: datetime, ends_at: datetime, reason: str) -> BarberTimeOff:
        item = BarberTimeOff(barber_id=barber_id, starts_at=starts_at, ends_at=ends_at, reason=reason)
        self._session.add(item)
        return item

    async def list_for_barber(self, barber_id: UUID) -> list[BarberTimeOff]:
        result = await self._session.scalars(select(BarberTimeOff).where(BarberTimeOff.barber_id == barber_id).order_by(BarberTimeOff.starts_at))
        return list(result.all())

    async def list_overlapping(self, *, barber_id: UUID, starts_at: datetime, ends_at: datetime) -> list[BarberTimeOff]:
        statement = select(BarberTimeOff).where(BarberTimeOff.barber_id == barber_id, BarberTimeOff.starts_at < ends_at, BarberTimeOff.ends_at > starts_at)
        result = await self._session.scalars(statement)
        return list(result.all())

    async def delete(self, *, barber_id: UUID, item_id: UUID) -> bool:
        result = await self._session.execute(delete(BarberTimeOff).where(BarberTimeOff.id == item_id, BarberTimeOff.barber_id == barber_id))
        return bool(result.rowcount)
