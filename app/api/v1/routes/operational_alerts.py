"""Authenticated tools for validating operational alert delivery."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies import require_primary_owner
from app.core.config import get_settings
from app.models.user import User
from app.services.operational_alerts import OperationalAlert, dispatch_operational_alert

router = APIRouter(prefix="/operational-alerts")


@router.post(
    "/test",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Send a safe Discord delivery test",
)
async def send_operational_alert_test(
    request: Request,
    current_user: Annotated[User, Depends(require_primary_owner)],
) -> None:
    """Send a non-error Discord message without creating a simulated production failure."""
    del current_user
    delivered = await dispatch_operational_alert(
        OperationalAlert(
            category="integration",
            event="delivery_test",
            severity="info",
            status_code=200,
            route="/api/v1/operational-alerts/test",
        ),
        request_id=getattr(request.state, "request_id", None),
        settings=get_settings(),
        deduplicate=False,
    )
    if not delivered:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Discord alert could not be delivered.",
        )
