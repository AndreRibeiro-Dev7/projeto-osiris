import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SchedulingConflictError
from app.schemas.appointment import AppointmentRescheduleRequest
from app.schemas.public_booking import PublicBookingCreate
from app.services.public_booking import PublicBookingService

NOW = datetime(2026, 10, 27, 14, 14, tzinfo=UTC)


@pytest.mark.parametrize("minutes_ago", [0, 14, 24 * 60])
def test_public_booking_rejects_elapsed_starts_before_creating_customer(
    minutes_ago: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = AsyncMock(spec=AsyncSession)
    service = PublicBookingService(session)
    customer_lookup = AsyncMock()
    service._customers = SimpleNamespace(get_by_business_and_phone=customer_lookup)
    monkeypatch.setattr("app.services.public_booking.utc_now", lambda: NOW)
    payload = PublicBookingCreate(
        customer_name="Test client",
        customer_phone="00000000001",
        barber_id=uuid4(),
        service_id=uuid4(),
        starts_at=NOW - timedelta(minutes=minutes_ago),
    )

    with pytest.raises(SchedulingConflictError, match="horário já passou"):
        asyncio.run(service.create(uuid4(), payload))

    customer_lookup.assert_not_awaited()
    session.flush.assert_not_awaited()
    session.commit.assert_not_awaited()


def test_public_reschedule_rejects_elapsed_starts(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock(spec=AsyncSession)
    service = PublicBookingService(session)
    service._appointments = SimpleNamespace(
        get_by_public_token=AsyncMock(return_value=SimpleNamespace(id=uuid4(), business_id=uuid4()))
    )
    reschedule = AsyncMock()
    monkeypatch.setattr("app.services.public_booking.AppointmentService.reschedule", reschedule)
    monkeypatch.setattr("app.services.public_booking.utc_now", lambda: NOW)
    payload = AppointmentRescheduleRequest(barber_id=uuid4(), service_id=uuid4(), starts_at=NOW)

    with pytest.raises(SchedulingConflictError, match="horário já passou"):
        asyncio.run(service.reschedule(uuid4(), payload))

    reschedule.assert_not_awaited()
    session.commit.assert_not_awaited()
