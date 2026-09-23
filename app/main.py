"""FastAPI application entry point."""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from app.api.v1.router import router as api_v1_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    """Create and configure the HTTP application."""
    settings = get_settings()
    production = settings.environment.lower() == "production"
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="API for the Projeto Osiris intelligent scheduling platform.",
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
    )

    @application.middleware("http")
    async def add_security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Apply browser security controls to API and dashboard responses."""
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; "
            "form-action 'self'; object-src 'none'; img-src 'self' data:; "
            "script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "connect-src 'self'"
        )
        if production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    application.include_router(api_v1_router, prefix=settings.api_v1_prefix)
    application.mount("/dashboard", StaticFiles(directory="dist", html=True), name="dashboard")
    return application


app = create_app()
