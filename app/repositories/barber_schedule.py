"""Database queries for recurring barber schedules."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.barber_schedule import BarberSchedule
from app.schemas.availability import BarberScheduleUpsert


class BarberScheduleRepository:
    """Persist and retrieve weekly working windows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, barber_id: UUID, weekday: int) -> BarberSchedule | None:
        """Return a barber's schedule for one weekday."""
        statement = select(BarberSchedule).where(
            BarberSchedule.barber_id == barber_id,
            BarberSchedule.weekday == weekday,
        )
        result = await self._session.scalars(statement)
        return result.one_or_none()

    async def upsert(
        self,
        *,
        barber_id: UUID,
        weekday: int,
        payload: BarberScheduleUpsert,
    ) -> BarberSchedule:
        """Create or replace one recurring working window."""
        schedule = await self.get(barber_id, weekday)
        if schedule is None:
            schedule = BarberSchedule(barber_id=barber_id, weekday=weekday)
            self._session.add(schedule)

        schedule.starts_at = payload.starts_at
        schedule.ends_at = payload.ends_at
        schedule.slot_duration_minutes = payload.slot_duration_minutes
        return schedule
