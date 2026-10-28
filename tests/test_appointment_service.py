import asyncio
from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InvalidAppointmentStatusTransitionError,
    InvalidSchedulingReferenceError,
    ResourceNotFoundError,
)
from app.models.appointment import Appointment, AppointmentStatus
from app.repositories.appointment import AppointmentRepository
from app.services.appointment import AppointmentService

BUSINESS_ID = UUID("b932827e-a7b0-46b2-9d9e-d30419f89777")


def make_appointment(status: AppointmentStatus) -> Appointment:
    starts_at = datetime(2026, 8, 10, 13, tzinfo=UTC)
    return Appointment(
        id=uuid4(),
        business_id=BUSINESS_ID,
        barber_id=uuid4(),
        customer_id=uuid4(),
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=30),
        status=status,
        notes="Corte e barba",
    )


def make_service(appointment: Appointment | None) -> tuple[AppointmentService, AsyncMock]:
    session_mock = AsyncMock(spec=AsyncSession)
    service = AppointmentService(cast(AsyncSession, session_mock))
    repository_mock = AsyncMock(spec=AppointmentRepository)
    repository_mock.get_by_id_for_update.return_value = appointment
    service._appointments = cast(AppointmentRepository, repository_mock)
    return service, session_mock


def test_confirm_changes_scheduled_appointment_to_confirmed() -> None:
    appointment = make_appointment(AppointmentStatus.SCHEDULED)
    service, session_mock = make_service(appointment)

    result = asyncio.run(service.confirm(BUSINESS_ID, appointment.id))

    assert result.status is AppointmentStatus.CONFIRMED
    session_mock.commit.assert_awaited_once()
    session_mock.refresh.assert_awaited_once_with(appointment)


@pytest.mark.parametrize(
    "initial_status", [AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED]
)
def test_cancel_changes_active_appointment_to_cancelled(
    initial_status: AppointmentStatus,
) -> None:
    appointment = make_appointment(initial_status)
    service, session_mock = make_service(appointment)

    result = asyncio.run(service.cancel(BUSINESS_ID, appointment.id))

    assert result.status is AppointmentStatus.CANCELLED
    session_mock.commit.assert_awaited_once()
    session_mock.refresh.assert_awaited_once_with(appointment)


def test_confirm_rejects_cancelled_appointment() -> None:
    appointment = make_appointment(AppointmentStatus.CANCELLED)
    service, session_mock = make_service(appointment)

    with pytest.raises(
        InvalidAppointmentStatusTransitionError,
        match="Cannot change an appointment from cancelled to confirmed",
    ):
        asyncio.run(service.confirm(BUSINESS_ID, appointment.id))

    session_mock.commit.assert_not_awaited()


def test_status_change_rejects_appointment_from_another_business() -> None:
    appointment = make_appointment(AppointmentStatus.SCHEDULED)
    service, session_mock = make_service(appointment)

    with pytest.raises(InvalidSchedulingReferenceError):
        asyncio.run(service.confirm(uuid4(), appointment.id))

    session_mock.commit.assert_not_awaited()


def test_status_change_rejects_unknown_appointment() -> None:
    service, session_mock = make_service(None)

    with pytest.raises(ResourceNotFoundError):
        asyncio.run(service.confirm(BUSINESS_ID, uuid4()))

    session_mock.commit.assert_not_awaited()


@pytest.mark.parametrize("closed", [True, False])
def test_reschedule_checks_closure_and_locks_destination_barber(
    monkeypatch: pytest.MonkeyPatch, closed: bool
) -> None:
    from app.core.exceptions import SchedulingConflictError
    from app.models.barber import Barber
    from app.models.business import Business
    from app.models.service import Service
    from app.schemas.appointment import AppointmentRescheduleRequest

    appointment = make_appointment(AppointmentStatus.SCHEDULED)
    service, session = make_service(appointment)
    business = Business(id=BUSINESS_ID, timezone="America/Sao_Paulo")
    barber = Barber(id=uuid4(), business_id=BUSINESS_ID, is_active=True)
    cut = Service(
        id=uuid4(), business_id=BUSINESS_ID, is_active=True, duration_minutes=30, price_cents=2500
    )
    monkeypatch.setattr(service._businesses, "get_by_id", AsyncMock(return_value=business))
    closure = AsyncMock(return_value=object() if closed else None)
    monkeypatch.setattr(service._closures, "get_for_date", closure)
    locked_barber = AsyncMock(return_value=barber)
    monkeypatch.setattr(service._barbers, "get_by_id_for_update", locked_barber)
    monkeypatch.setattr(service._services, "get_by_id", AsyncMock(return_value=cut))
    conflict = AsyncMock(return_value=False)
    monkeypatch.setattr(service._appointments, "has_active_conflict", conflict)
    # 01:00 UTC is still the previous business day in São Paulo.
    new_start = datetime(2030, 1, 17, 1, tzinfo=UTC)
    original_start = appointment.starts_at
    payload = AppointmentRescheduleRequest(
        barber_id=barber.id, service_id=cut.id, starts_at=new_start
    )
    if closed:
        with pytest.raises(SchedulingConflictError, match="closed"):
            asyncio.run(service.reschedule(BUSINESS_ID, appointment.id, payload))
        session.commit.assert_not_awaited()
        locked_barber.assert_not_awaited()
        assert appointment.starts_at == original_start
    else:
        result = asyncio.run(service.reschedule(BUSINESS_ID, appointment.id, payload))
        locked_barber.assert_awaited_once_with(barber.id)
        conflict.assert_awaited_once_with(
            barber_id=barber.id,
            starts_at=new_start,
            ends_at=new_start + timedelta(minutes=30),
            exclude_appointment_id=appointment.id,
        )
        session.commit.assert_awaited_once()
        assert result.starts_at == new_start
    closure.assert_awaited_once_with(BUSINESS_ID, new_start.date() - timedelta(days=1))
