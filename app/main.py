"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.v1.router import router as api_v1_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    """Create and configure the HTTP application."""
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="API for the Projeto Osiris intelligent scheduling platform.",
    )
    application.include_router(api_v1_router, prefix=settings.api_v1_prefix)
    return application


app = create_app()
