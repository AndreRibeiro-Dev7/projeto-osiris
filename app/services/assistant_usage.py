"""Serialize per-business admission counters before starting business workflows."""

import math
from datetime import timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_now
from app.models.assistant_usage import AssistantUsage
from app.models.public_booking_usage import PublicBookingUsage


class BusinessRateLimited(Exception):
    def __init__(self, seconds: int) -> None:
        self.seconds = max(1, seconds)


class BusinessUsageService:
    def __init__(
        self, session: AsyncSession, model: type[AssistantUsage] | type[PublicBookingUsage]
    ) -> None:
        self.session = session
        self.model = model

    async def consume(self, business_id: UUID, *, per_minute: int, per_hour: int) -> None:
        """Reserve one attempt in a transaction committed before the business workflow.

        Invoke only after business validation and before any business writes.
        Provider errors consume quota too; a booking rollback must not undo it.
        """
        now = utc_now()
        await self.session.execute(
            insert(self.model)
            .values(
                business_id=business_id,
                minute_started_at=now,
                minute_requests=0,
                hour_started_at=now,
                hour_requests=0,
            )
            .on_conflict_do_nothing(index_elements=["business_id"])
        )
        row = cast(
            AssistantUsage | PublicBookingUsage,
            (
                await self.session.scalars(
                    select(self.model)
                    .where(self.model.business_id == business_id)
                    .with_for_update()
                )
            ).one(),
        )
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
            raise BusinessRateLimited(math.ceil(max(waits)))
        row.minute_requests += 1
        row.hour_requests += 1
        await self.session.commit()


# Keep the assistant's public service interface and exception imports unchanged.
AssistantRateLimited = BusinessRateLimited


class AssistantUsageService(BusinessUsageService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AssistantUsage)
