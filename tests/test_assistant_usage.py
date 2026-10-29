"""Quota boundaries and rejection before provider construction."""

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_business_access
from app.core.config import Settings
from app.database.session import get_db_session
from app.main import app
from app.models.assistant_usage import AssistantUsage
from app.services.assistant_usage import AssistantRateLimited, AssistantUsageService


@pytest.mark.parametrize(
    ("minute", "hour", "minute_age", "hour_age", "wait", "expected"),
    [
        (0, 0, 0, 0, None, (1, 1)),
        (20, 40, 0, 0, 60, (20, 40)),
        (20, 200, 30, 10, 3590, (20, 200)),
        (20, 200, 60, 3600, None, (1, 1)),
        (20, 199, 60, 10, None, (1, 200)),
        (19, 200, 0, 3600, None, (20, 1)),
    ],
)
def test_quota_windows(
    monkeypatch: pytest.MonkeyPatch,
    minute: int,
    hour: int,
    minute_age: int,
    hour_age: int,
    wait: int | None,
    expected: tuple[int, int],
) -> None:
    now = datetime(2026, 10, 28, 14, tzinfo=UTC)
    monkeypatch.setattr("app.services.assistant_usage.utc_now", lambda: now)
    row = AssistantUsage(
        business_id=uuid4(),
        minute_started_at=now - timedelta(seconds=minute_age),
        minute_requests=minute,
        hour_started_at=now - timedelta(seconds=hour_age),
        hour_requests=hour,
    )
    result = MagicMock()
    result.one.return_value = row
    session = AsyncMock(spec=AsyncSession)
    session.scalars.return_value = result
    service = AssistantUsageService(cast(AsyncSession, session))
    if wait is None:
        asyncio.run(service.consume(row.business_id, per_minute=20, per_hour=200))
    else:
        with pytest.raises(AssistantRateLimited) as error:
            asyncio.run(service.consume(row.business_id, per_minute=20, per_hour=200))
        assert error.value.seconds == wait
    assert (row.minute_requests, row.hour_requests) == expected
    session.commit.assert_awaited_once()


def test_limited_request_returns_wait_without_constructing_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        openai_api_key="simulated",
        openai_model="simulated",
        assistant_requests_per_minute=20,
        assistant_requests_per_hour=200,
    )
    monkeypatch.setattr("app.api.v1.routes.businesses.get_settings", lambda: settings)
    consume = AsyncMock(side_effect=AssistantRateLimited(45))
    monkeypatch.setattr(AssistantUsageService, "consume", consume)
    provider = MagicMock(side_effect=AssertionError("Provider must not be called"))
    monkeypatch.setattr("app.api.v1.routes.businesses.OpenAIResponsesClient", provider)

    async def fake_session():
        yield AsyncMock(spec=AsyncSession)

    app.dependency_overrides[require_business_access] = lambda: None
    app.dependency_overrides[get_db_session] = fake_session
    try:
        response = TestClient(app).post(
            f"/api/v1/businesses/{uuid4()}/assistant/messages",
            json={"barber_id": str(uuid4()), "appointment_date": "2030-01-16", "message": "Teste"},
        )
        assert response.status_code == 429
        assert response.headers["retry-after"] == "45"
        assert "45 segundos" in response.json()["detail"]
        assert "agenda manual" in response.json()["detail"]
        provider.assert_not_called()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("name", ["assistant_requests_per_minute", "assistant_requests_per_hour"])
def test_assistant_limits_cannot_be_disabled_with_zero(name: str) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{name: 0})
