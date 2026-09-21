"""Routes exposed by API version 1."""

from fastapi import APIRouter

from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.businesses import router as businesses_router
from app.api.v1.routes.database_health import router as database_health_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.public_booking import router as public_booking_router

router = APIRouter()
router.include_router(auth_router, tags=["authentication"])
router.include_router(health_router, tags=["health"])
router.include_router(database_health_router, tags=["health"])
router.include_router(businesses_router, tags=["businesses"])
router.include_router(public_booking_router, tags=["public-booking"])
