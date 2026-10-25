"""Privacy-safe operational alerts for authentication and external providers."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from threading import Lock
from time import monotonic
from typing import Literal

import httpx

from app.core.config import Settings, get_settings

AlertCategory = Literal["login", "email", "ai", "integration"]
AlertSeverity = Literal["warning", "error", "critical"]

logger = logging.getLogger("app.operations")
_delivery_lock = Lock()
_last_delivery_by_key: dict[str, float] = {}


@dataclass(frozen=True, slots=True)
class OperationalAlert:
    """Non-sensitive metadata describing one actionable production failure."""

    category: AlertCategory
    event: str
    severity: AlertSeverity
    status_code: int | None = None
    route: str | None = None


def classify_operational_failure(*, route: str, status_code: int) -> OperationalAlert | None:
    """Map monitored HTTP failures to stable alert categories."""
    if route.endswith("/auth/token") and (status_code == 429 or status_code >= 500):
        event = "account_locked" if status_code == 429 else "login_unavailable"
        return OperationalAlert("login", event, "warning", status_code, route)

    email_route = any(marker in route for marker in ("/auth/password-reset/", "/auth/email/"))
    if email_route and status_code >= 500:
        return OperationalAlert("email", "email_delivery_failed", "error", status_code, route)

    if route.endswith("/assistant/messages") and status_code >= 500:
        return OperationalAlert("ai", "ai_provider_failed", "error", status_code, route)

    if any(marker in route for marker in ("/integrations/", "/webhooks/")) and status_code >= 500:
        return OperationalAlert(
            "integration", "external_integration_failed", "error", status_code, route
        )

    return None


def _reserve_delivery(key: str, cooldown_seconds: int) -> bool:
    now = monotonic()
    with _delivery_lock:
        last_delivery = _last_delivery_by_key.get(key)
        if last_delivery is not None and now - last_delivery < cooldown_seconds:
            return False
        _last_delivery_by_key[key] = now
        return True


def _release_delivery(key: str) -> None:
    with _delivery_lock:
        _last_delivery_by_key.pop(key, None)


async def dispatch_operational_alert(
    alert: OperationalAlert,
    *,
    request_id: str | None = None,
    settings: Settings | None = None,
) -> bool:
    """Log an alert and optionally deliver a deduplicated webhook notification."""
    current_settings = settings or get_settings()
    log_fields = {
        "event": "operational.alert",
        "alert_category": alert.category,
        "alert_event": alert.event,
        "alert_severity": alert.severity,
        "request_id": request_id,
        "route": alert.route,
        "status_code": alert.status_code,
    }
    alert_summary = (
        f"operational.alert category={alert.category} name={alert.event} "
        f"severity={alert.severity}"
    )
    logger.error(alert_summary, extra=log_fields)

    if not current_settings.operational_alert_webhook_url:
        return False

    delivery_key = f"{alert.category}:{alert.event}"
    if not _reserve_delivery(delivery_key, current_settings.operational_alert_cooldown_seconds):
        logger.info(
            f"{alert_summary} delivery=suppressed",
            extra={**log_fields, "event": "operational.alert_suppressed"},
        )
        return False

    payload = {
        "source": "projeto-osiris",
        "environment": current_settings.environment,
        **asdict(alert),
        "request_id": request_id,
    }
    try:
        async with httpx.AsyncClient(
            timeout=current_settings.operational_alert_timeout_seconds
        ) as client:
            response = await client.post(
                current_settings.operational_alert_webhook_url,
                json=payload,
            )
            response.raise_for_status()
    except httpx.HTTPError:
        _release_delivery(delivery_key)
        logger.exception(
            f"{alert_summary} delivery=failed",
            extra={**log_fields, "event": "operational.alert_delivery_failed"},
        )
        return False

    logger.info(
        f"{alert_summary} delivery=sent",
        extra={**log_fields, "event": "operational.alert_delivered"},
    )
    return True


def reset_operational_alert_cooldowns() -> None:
    """Clear process-local delivery reservations for deterministic tests."""
    with _delivery_lock:
        _last_delivery_by_key.clear()
