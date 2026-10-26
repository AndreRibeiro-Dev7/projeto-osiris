"""FastAPI application entry point."""

import logging
from collections.abc import Awaitable, Callable
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from app.api.v1.router import router as api_v1_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.database.session import async_session_factory
from app.services.audit import record_activity
from app.services.operational_alerts import (
    classify_operational_failure,
    dispatch_operational_alert,
)
from app.services.operational_metrics import record_critical_operation_metric

logger = logging.getLogger(__name__)
request_logger = logging.getLogger("app.http")


def create_app() -> FastAPI:
    """Create and configure the HTTP application."""
    settings = get_settings()
    production = settings.environment.lower() == "production"
    configure_logging(
        level=settings.log_level,
        json_logs=production or settings.log_json,
    )
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
        current_user = getattr(request.state, "current_user", None)
        if (
            current_user is not None
            and request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and 200 <= response.status_code < 400
        ):
            try:
                async with async_session_factory() as session:
                    await record_activity(
                        session,
                        user=current_user,
                        method=request.method,
                        path=request.url.path,
                    )
            except Exception:
                logger.exception("Could not persist the audit activity")
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

    @application.middleware("http")
    async def log_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Log safe request metadata without bodies, query strings, tokens, or IPs."""

        def route_template() -> str:
            route = getattr(request.scope.get("route"), "path", "<unmatched>")
            if (
                route != "<unmatched>"
                and request.url.path.startswith(f"{settings.api_v1_prefix}/")
                and not route.startswith(settings.api_v1_prefix)
            ):
                return f"{settings.api_v1_prefix}{route}"
            return route

        request_id = uuid4().hex
        request.state.request_id = request_id
        started_at = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((perf_counter() - started_at) * 1000, 2)
            request_logger.exception(
                "request.failed",
                extra={
                    "event": "request.failed",
                    "request_id": request_id,
                    "method": request.method,
                    "route": route_template(),
                    "status_code": 500,
                    "duration_ms": duration_ms,
                },
            )
            raise

        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        request_logger.log(
            logging.WARNING if response.status_code >= 500 else logging.INFO,
            "request.completed",
            extra={
                "event": "request.completed",
                "request_id": request_id,
                "method": request.method,
                "route": route_template(),
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        record_critical_operation_metric(
            method=request.method,
            route=route_template(),
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id,
        )
        operational_alert = classify_operational_failure(
            route=route_template(),
            status_code=response.status_code,
        )
        if operational_alert is not None:
            await dispatch_operational_alert(
                operational_alert,
                request_id=request_id,
                settings=settings,
            )
        response.headers["X-Request-ID"] = request_id
        return response

    application.include_router(api_v1_router, prefix=settings.api_v1_prefix)
    application.mount("/dashboard", StaticFiles(directory="dist", html=True), name="dashboard")
    return application


app = create_app()
