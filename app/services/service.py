"""Use cases for the service catalog."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateResourceError, ResourceNotFoundError
from app.models.service import Service
from app.repositories.business import BusinessRepository
from app.repositories.service import ServiceRepository
from app.schemas.service import ServiceCreate, ServiceUpdate


class ServiceCatalogService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._businesses = BusinessRepository(session)
        self._services = ServiceRepository(session)

    async def create(self, business_id: UUID, payload: ServiceCreate) -> Service:
        if await self._businesses.get_by_id(business_id) is None:
            raise ResourceNotFoundError("Business not found.")
        if await self._services.get_by_name(business_id, payload.name):
            raise DuplicateResourceError("A service with this name already exists.")
        service = await self._services.create(business_id, **payload.model_dump())
        try:
            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            raise DuplicateResourceError("A service with this name already exists.") from error
        await self._session.refresh(service)
        return service

    async def list(self, business_id: UUID) -> list[Service]:
        if await self._businesses.get_by_id(business_id) is None:
            raise ResourceNotFoundError("Business not found.")
        return await self._services.list_by_business(business_id)

    async def update(self, business_id: UUID, service_id: UUID, payload: ServiceUpdate) -> Service:
        service = await self._services.get_by_id(service_id)
        if service is None or service.business_id != business_id:
            raise ResourceNotFoundError("Service not found.")
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(service, field, value)
        try:
            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            raise DuplicateResourceError("A service with this name already exists.") from error
        await self._session.refresh(service)
        return service
