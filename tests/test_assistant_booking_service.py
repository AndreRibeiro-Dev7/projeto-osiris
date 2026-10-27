import asyncio
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import SchedulingConflictError
from app.schemas.availability import AvailabilityResponse, AvailabilitySlot
from app.services.assistant_booking import AssistantBookingService


def make_service(*, available: bool = True, booked: bool = False):
    start = datetime(2030, 1, 17, 12, tzinfo=UTC)
    appointment = SimpleNamespace(id=uuid4())
    proposal = SimpleNamespace(
        id=uuid4(),
        business_id=uuid4(),
        barber_id=uuid4(),
        customer_id=uuid4(),
        appointment_date=date(2030, 1, 17),
        proposed_starts_at=start,
        proposed_ends_at=start + timedelta(minutes=30),
        appointment_id=appointment.id if booked else None,
    )
    service = AssistantBookingService.__new__(AssistantBookingService)
    service._session = SimpleNamespace(commit=AsyncMock())
    service._conversations = SimpleNamespace(get_for_update=AsyncMock(return_value=proposal))
    service._barbers = SimpleNamespace(get_by_id_for_update=AsyncMock())
    service._availability = SimpleNamespace(
        list_available_slots=AsyncMock(
            return_value=AvailabilityResponse(
                business_id=proposal.business_id,
                barber_id=proposal.barber_id,
                appointment_date=proposal.appointment_date,
                timezone="America/Sao_Paulo",
                slots=(
                    [AvailabilitySlot(starts_at=start, ends_at=proposal.proposed_ends_at)]
                    if available
                    else []
                ),
            )
        )
    )
    service._appointments = SimpleNamespace(
        create=AsyncMock(return_value=appointment), get=AsyncMock(return_value=appointment)
    )
    return service, proposal, appointment


def test_confirmation_links_reservation_before_single_commit() -> None:
    service, proposal, appointment = make_service()

    async def commit():
        assert proposal.appointment_id == appointment.id

    service._session.commit.side_effect = commit
    result = asyncio.run(
        service.confirm(
            business_id=proposal.business_id,
            barber_id=proposal.barber_id,
            conversation_id=proposal.id,
        )
    )

    assert result is appointment
    assert service._appointments.create.await_args.kwargs == {"commit": False}
    service._session.commit.assert_awaited_once()


def test_confirmation_rejects_a_slot_removed_after_proposal() -> None:
    service, proposal, _ = make_service(available=False)

    with pytest.raises(SchedulingConflictError):
        asyncio.run(
            service.confirm(
                business_id=proposal.business_id,
                barber_id=proposal.barber_id,
                conversation_id=proposal.id,
            )
        )

    service._appointments.create.assert_not_awaited()
    service._session.commit.assert_not_awaited()
    assert proposal.appointment_id is None


def test_retry_returns_existing_reservation_without_creating_another() -> None:
    service, proposal, appointment = make_service(available=False, booked=True)

    result = asyncio.run(
        service.confirm(
            business_id=proposal.business_id,
            barber_id=proposal.barber_id,
            conversation_id=proposal.id,
        )
    )

    assert result is appointment
    service._appointments.get.assert_awaited_once_with(appointment.id)
    service._appointments.create.assert_not_awaited()
    service._availability.list_available_slots.assert_not_awaited()
    service._session.commit.assert_not_awaited()
