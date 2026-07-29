"""Health endpoint used by people and infrastructure."""

from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="Check API availability")
async def health_check() -> HealthResponse:
    """Return basic information confirming that the API is online."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        application=settings.app_name,
        version=settings.app_version,
    )
