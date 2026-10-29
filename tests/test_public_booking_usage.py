"""Reject excess public writes before creating customers or reservations."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.database.session import get_db_session
from app.main import app
from app.services.assistant_usage import BusinessRateLimited, BusinessUsageService
from app.services.public_booking import PublicBookingService


@pytest.mark.parametrize("exists", [True, False])
def test_public_admission_rejects_before_booking_writes(
    monkeypatch: pytest.MonkeyPatch,
    exists: bool,
) -> None:
    from app.repositories.business import BusinessRepository

    business_id = uuid4()
    lookup = AsyncMock(return_value=SimpleNamespace(id=business_id) if exists else None)
    monkeypatch.setattr(BusinessRepository, "get_by_id", lookup)
    consume = AsyncMock(side_effect=BusinessRateLimited(45))
    monkeypatch.setattr(BusinessUsageService, "consume", consume)
    create = AsyncMock(side_effect=AssertionError("No booking writes are allowed"))
    monkeypatch.setattr(PublicBookingService, "create", create)
    settings = Settings(
        _env_file=None, public_booking_requests_per_minute=20, public_booking_requests_per_hour=200
    )
    monkeypatch.setattr("app.api.v1.routes.public_booking.get_settings", lambda: settings)

    async def fake_session():
        yield AsyncMock(spec=AsyncSession)

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db_session] = fake_session
    try:
        response = TestClient(app).post(
            f"/api/v1/public/businesses/{business_id}/appointments",
            headers={"X-Forwarded-For": "192.0.2.1"},
            json={
                "barber_id": str(uuid4()),
                "service_id": str(uuid4()),
                "customer_name": "Test client",
                "customer_phone": "00000000001",
                "starts_at": "2030-01-16T09:00:00-03:00",
            },
        )
        assert response.status_code == (429 if exists else 404)
        create.assert_not_awaited()
        if exists:
            consume.assert_awaited_once_with(business_id, per_minute=20, per_hour=200)
            assert response.headers["retry-after"] == "45"
            assert "45 segundos" in response.json()["detail"]
        else:
            consume.assert_not_awaited()
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest.mark.parametrize(
    "field", ["public_booking_requests_per_minute", "public_booking_requests_per_hour"]
)
@pytest.mark.parametrize("value", [0, -1])
def test_public_quotas_must_be_positive(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})
