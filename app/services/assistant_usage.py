"""Serialize assistant quota decisions before contacting the external model."""

import math
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_now
from app.models.assistant_usage import AssistantUsage


class AssistantRateLimited(Exception):
    def __init__(self, seconds: int) -> None:
        self.seconds = max(1, seconds)


class AssistantUsageService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def consume(self, business_id: UUID, *, per_minute: int, per_hour: int) -> None:
        """Reserve one attempt in a transaction committed before the AI workflow.

        Invoke only at the start of the authenticated route, before business writes.
        Provider errors consume quota too; a booking rollback must not undo it.
        """
        now = utc_now()
        await self.session.execute(
            insert(AssistantUsage)
            .values(
                business_id=business_id,
                minute_started_at=now,
                minute_requests=0,
                hour_started_at=now,
                hour_requests=0,
            )
            .on_conflict_do_nothing(index_elements=["business_id"])
        )
        row = (
            await self.session.scalars(
                select(AssistantUsage)
                .where(AssistantUsage.business_id == business_id)
                .with_for_update()
            )
        ).one()
        # Re-read time after waiting for a competing worker's transaction.
        now = utc_now()
        if now >= row.minute_started_at + timedelta(minutes=1):
            row.minute_started_at, row.minute_requests = now, 0
        if now >= row.hour_started_at + timedelta(hours=1):
            row.hour_started_at, row.hour_requests = now, 0
        waits = []
        if row.minute_requests >= per_minute:
            waits.append((row.minute_started_at + timedelta(minutes=1) - now).total_seconds())
        if row.hour_requests >= per_hour:
            waits.append((row.hour_started_at + timedelta(hours=1) - now).total_seconds())
        if waits:
            await self.session.commit()
            raise AssistantRateLimited(math.ceil(max(waits)))
        row.minute_requests += 1
        row.hour_requests += 1
        await self.session.commit()
