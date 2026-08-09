"""Database availability endpoint."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db_session, is_database_available
from app.schemas.health import DatabaseHealthResponse

router = APIRouter()


@router.get(
    "/health/database",
    response_model=DatabaseHealthResponse,
    summary="Check database availability",
)
async def database_health_check(
    session: AsyncSession = Depends(get_db_session),
) -> DatabaseHealthResponse:
    """Report whether PostgreSQL is reachable by the application."""
    try:
        await is_database_available(session)
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable.",
        ) from error

    return DatabaseHealthResponse(status="ok")
