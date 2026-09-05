import asyncio
from datetime import UTC, date, datetime, time
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InactiveBarberError
from app.models.appointment import Appointment, AppointmentStatus
from app.models.barber import Barber
from app.models.barber_schedule import BarberSchedule
from app.models.business import Business
from app.repositories.appointment import AppointmentRepository
from app.repositories.barber import BarberRepository
from app.repositories.barber_schedule import BarberScheduleRepository
from app.repositories.business import BusinessRepository
from app.services.availability import AvailabilityService

BUSINESS_ID = UUID("b932827e-a7b0-46b2-9d9e-d30419f89777")
BARBER_ID = UUID("0d15a1e1-31bd-437d-809f-71cfbe12569e")
MONDAY = date(2026, 9, 7)


def make_service(
    *,
    schedule: BarberSchedule | None,
    appointments: list[Appointment] | None = None,
    barber_active: bool = True,
) -> AvailabilityService:
    session_mock = AsyncMock(spec=AsyncSession)
    service = AvailabilityService(cast(AsyncSession, session_mock))

    business_repository = AsyncMock(spec=BusinessRepository)
    business_repository.get_by_id.return_value = Business(
        id=BUSINESS_ID,
        name="Barbearia Osiris",
        phone="5511999999999",
        timezone="America/Sao_Paulo",
    )
    barber_repository = AsyncMock(spec=BarberRepository)
    barber_repository.get_by_id.return_value = Barber(
        id=BARBER_ID,
        business_id=BUSINESS_ID,
        full_name="André",
        phone="5511888888888",
        is_active=barber_active,
    )
    schedule_repository = AsyncMock(spec=BarberScheduleRepository)
    schedule_repository.get.return_value = schedule
    appointment_repository = AsyncMock(spec=AppointmentRepository)
    appointment_repository.list_active_overlapping.return_value = appointments or []

    service._businesses = cast(BusinessRepository, business_repository)
    service._barbers = cast(BarberRepository, barber_repository)
    service._schedules = cast(BarberScheduleRepository, schedule_repository)
    service._appointments = cast(AppointmentRepository, appointment_repository)
    return service


def make_monday_schedule() -> BarberSchedule:
    return BarberSchedule(
        id=uuid4(),
        barber_id=BARBER_ID,
        weekday=0,
        starts_at=time(9),
        ends_at=time(11),
        slot_duration_minutes=30,
    )


def test_availability_excludes_slots_that_overlap_active_appointments() -> None:
    occupied = Appointment(
        id=uuid4(),
        business_id=BUSINESS_ID,
        barber_id=BARBER_ID,
        customer_id=uuid4(),
        starts_at=datetime(2026, 9, 7, 12, 30, tzinfo=UTC),
        ends_at=datetime(2026, 9, 7, 13, 0, tzinfo=UTC),
        status=AppointmentStatus.CONFIRMED,
    )
    service = make_service(schedule=make_monday_schedule(), appointments=[occupied])

    result = asyncio.run(
        service.list_available_slots(
            business_id=BUSINESS_ID,
            barber_id=BARBER_ID,
            appointment_date=MONDAY,
        )
    )

    assert [slot.starts_at.strftime("%H:%M") for slot in result.slots] == [
        "09:00",
        "10:00",
        "10:30",
    ]
    assert result.timezone == "America/Sao_Paulo"


def test_availability_is_empty_when_weekday_has_no_schedule() -> None:
    service = make_service(schedule=None)

    result = asyncio.run(
        service.list_available_slots(
            business_id=BUSINESS_ID,
            barber_id=BARBER_ID,
            appointment_date=MONDAY,
        )
    )

    assert result.slots == []


def test_availability_rejects_inactive_barber() -> None:
    service = make_service(schedule=make_monday_schedule(), barber_active=False)

    with pytest.raises(InactiveBarberError):
        asyncio.run(
            service.list_available_slots(
                business_id=BUSINESS_ID,
                barber_id=BARBER_ID,
                appointment_date=MONDAY,
            )
        )
