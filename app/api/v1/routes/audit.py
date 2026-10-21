"""Owner-only access to the immutable business activity history."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_business_access
from app.database.session import get_db_session
from app.models.user import User
from app.repositories.audit_log import AuditLogRepository
from app.schemas.audit_log import AuditLogResponse

router = APIRouter(prefix="/businesses/{business_id}/audit-logs")


@router.get("", response_model=list[AuditLogResponse])
async def list_audit_logs(
    business_id: UUID,
    current_user: Annotated[User, Depends(require_business_access)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    area: Annotated[str | None, Query(max_length=40)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[AuditLogResponse]:
    """Return the newest successful changes for the authenticated business."""
    del current_user
    items = await AuditLogRepository(session).list_for_business(business_id, area=area, limit=limit)
    return [AuditLogResponse.model_validate(item) for item in items]
