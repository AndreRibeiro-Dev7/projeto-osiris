from datetime import date
from uuid import UUID
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.business_closure import BusinessClosure

class BusinessClosureRepository:
    def __init__(self, session: AsyncSession) -> None: self._session = session
    async def get_for_date(self, business_id: UUID, closure_date: date) -> BusinessClosure | None:
        result = await self._session.scalars(select(BusinessClosure).where(BusinessClosure.business_id == business_id, BusinessClosure.closure_date == closure_date)); return result.one_or_none()
    async def list(self, business_id: UUID) -> list[BusinessClosure]:
        result = await self._session.scalars(select(BusinessClosure).where(BusinessClosure.business_id == business_id).order_by(BusinessClosure.closure_date)); return list(result.all())
    async def create(self, business_id: UUID, closure_date: date, reason: str) -> BusinessClosure:
        item = BusinessClosure(business_id=business_id, closure_date=closure_date, reason=reason); self._session.add(item); return item
    async def delete(self, business_id: UUID, item_id: UUID) -> bool:
        result = await self._session.execute(delete(BusinessClosure).where(BusinessClosure.business_id == business_id, BusinessClosure.id == item_id)); return bool(result.rowcount)
