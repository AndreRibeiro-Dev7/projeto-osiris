"""Database queries for services."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service


class ServiceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, service_id: UUID) -> Service | None:
        return await self._session.get(Service, service_id)

    async def get_by_name(self, business_id: UUID, name: str) -> Service | None:
        result = await self._session.scalars(select(Service).where(Service.business_id == business_id, Service.name == name))
        return result.one_or_none()

    async def list_by_business(self, business_id: UUID) -> list[Service]:
        result = await self._session.scalars(select(Service).where(Service.business_id == business_id).order_by(Service.name))
        return list(result.all())

    async def create(self, business_id: UUID, **values: object) -> Service:
        service = Service(business_id=business_id, **values)
        self._session.add(service)
        return service
