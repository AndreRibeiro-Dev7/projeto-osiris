"""Queries for the immutable business activity history."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_business(
        self, business_id: UUID, *, area: str | None, limit: int
    ) -> list[AuditLog]:
        statement = select(AuditLog).where(AuditLog.business_id == business_id)
        if area:
            statement = statement.where(AuditLog.area == area)
        statement = statement.order_by(AuditLog.created_at.desc()).limit(limit)
        return list(await self._session.scalars(statement))
