import asyncio
from typing import Any

import httpx
import pytest

from app.core.config import Settings
from app.services.operational_alerts import (
    OperationalAlert,
    classify_operational_failure,
    dispatch_operational_alert,
    reset_operational_alert_cooldowns,
)


@pytest.mark.parametrize(
    ("route", "status_code", "category", "event"),
    [
        ("/api/v1/auth/token", 429, "login", "account_locked"),
        ("/api/v1/auth/email/request", 503, "email", "email_delivery_failed"),
        (
            "/api/v1/businesses/{business_id}/assistant/messages",
            502,
            "ai",
            "ai_provider_failed",
        ),
        (
            "/api/v1/integrations/calendar/sync",
            500,
            "integration",
            "external_integration_failed",
        ),
    ],
)
def test_classifies_actionable_operational_failures(
    route: str,
    status_code: int,
    category: str,
    event: str,
) -> None:
    alert = classify_operational_failure(route=route, status_code=status_code)

    assert alert is not None
    assert alert.category == category
    assert alert.event == event


def test_ignores_expected_client_errors() -> None:
    assert classify_operational_failure(route="/api/v1/auth/token", status_code=401) is None
    assert (
        classify_operational_failure(
            route="/api/v1/businesses/{business_id}/assistant/messages",
            status_code=422,
        )
        is None
    )


def test_dispatches_privacy_safe_payload_once_during_cooldown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    posted_payloads: list[dict[str, Any]] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == 2.0

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, *, json: dict[str, Any]) -> FakeResponse:
            assert url == "https://discord.com/api/webhooks/123/secret-token"
            posted_payloads.append(json)
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    reset_operational_alert_cooldowns()
    settings = Settings(
        discord_alert_webhook_url="https://discord.com/api/webhooks/123/secret-token",
        operational_alert_cooldown_seconds=300,
        operational_alert_timeout_seconds=2,
    )
    alert = OperationalAlert(
        category="ai",
        event="ai_provider_failed",
        severity="error",
        status_code=502,
        route="/api/v1/businesses/{business_id}/assistant/messages",
    )

    first_delivery = asyncio.run(
        dispatch_operational_alert(alert, request_id="request-123", settings=settings)
    )
    second_delivery = asyncio.run(
        dispatch_operational_alert(alert, request_id="request-456", settings=settings)
    )

    assert first_delivery is True
    assert second_delivery is False
    assert posted_payloads == [
        {
            "username": "Osiris Monitor",
            "allowed_mentions": {"parse": []},
            "embeds": [
                {
                    "title": "Alerta operacional do Osiris",
                    "description": (
                        "Uma falha que requer atenção foi detectada. "
                        "Consulte os logs da API usando o identificador abaixo."
                    ),
                    "color": 0xEF4444,
                    "fields": [
                        {"name": "Categoria", "value": "AI", "inline": True},
                        {"name": "Evento", "value": "ai_provider_failed", "inline": True},
                        {"name": "Ambiente", "value": "development", "inline": True},
                        {"name": "HTTP", "value": "502", "inline": True},
                        {
                            "name": "Rota",
                            "value": "`/api/v1/businesses/{business_id}/assistant/messages`",
                            "inline": False,
                        },
                    ],
                    "footer": {"text": "Request ID: request-123"},
                }
            ],
        }
    ]
    rendered_payload = str(posted_payloads[0]).lower()
    assert "password" not in rendered_payload
    assert "token" not in rendered_payload
    assert "email" not in rendered_payload


def test_webhook_failure_is_non_fatal_and_can_be_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    class FailingAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            pass

        async def __aenter__(self) -> "FailingAsyncClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, *, json: dict[str, Any]) -> None:
            nonlocal attempts
            attempts += 1
            raise httpx.ConnectError("alert endpoint unavailable")

    monkeypatch.setattr(httpx, "AsyncClient", FailingAsyncClient)
    reset_operational_alert_cooldowns()
    settings = Settings(
        discord_alert_webhook_url="https://discord.com/api/webhooks/123/secret-token",
    )
    alert = OperationalAlert("integration", "calendar_failed", "error", 503, "/webhooks")

    assert asyncio.run(dispatch_operational_alert(alert, settings=settings)) is False
    assert asyncio.run(dispatch_operational_alert(alert, settings=settings)) is False
    assert attempts == 2


def test_delivery_test_uses_safe_copy_and_bypasses_cooldown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    posted_payloads: list[dict[str, Any]] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            pass

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, *, json: dict[str, Any]) -> FakeResponse:
            posted_payloads.append(json)
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    reset_operational_alert_cooldowns()
    settings = Settings(
        discord_alert_webhook_url="https://discord.com/api/webhooks/123/secret-token",
        operational_alert_cooldown_seconds=300,
    )
    alert = OperationalAlert(
        "integration",
        "delivery_test",
        "info",
        200,
        "/api/v1/operational-alerts/test",
    )

    first = asyncio.run(dispatch_operational_alert(alert, settings=settings, deduplicate=False))
    second = asyncio.run(dispatch_operational_alert(alert, settings=settings, deduplicate=False))

    assert first is True
    assert second is True
    assert len(posted_payloads) == 2
    embed = posted_payloads[0]["embeds"][0]
    assert embed["title"] == "Teste de alertas do Osiris"
    assert embed["description"] == (
        "O canal do Discord está configurado corretamente. " "Nenhuma falha real foi detectada."
    )
    assert embed["color"] == 0x3B82F6
