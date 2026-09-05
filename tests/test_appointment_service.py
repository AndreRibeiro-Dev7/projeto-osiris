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
