import asyncio
from datetime import UTC, date, datetime, time
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from app.agents.availability_agent import AvailabilityAgent
from app.schemas.assistant import AssistantIntent, AssistantIntentName
from app.schemas.availability import AvailabilityResponse, AvailabilitySlot
from app.services.assistant_booking import AssistantBookingService
from app.services.availability import AvailabilityService

BUSINESS_ID = UUID("b932827e-a7b0-46b2-9d9e-d30419f89777")
BARBER_ID = UUID("0d15a1e1-31bd-437d-809f-71cfbe12569e")


class StubTextGenerationClient:
    """Record grounded model input and return a deterministic reply."""

    def __init__(self) -> None:
        self.instructions = ""
        self.user_input = ""
        self.intent = AssistantIntent(intent=AssistantIntentName.CHECK_AVAILABILITY)

    async def generate(self, *, instructions: str, user_input: str) -> str:
        self.instructions = instructions
        self.user_input = user_input
        return "Tenho horário às 09:00."

    async def interpret(
        self, *, instructions: str, user_input: str, response_format: type[BaseModel]
    ) -> BaseModel:
        return self.intent


def test_agent_generates_reply_grounded_in_available_slots() -> None:
    timezone = ZoneInfo("America/Sao_Paulo")
    availability_service = AsyncMock(spec=AvailabilityService)
    availability_service.list_available_slots.return_value = AvailabilityResponse(
        business_id=BUSINESS_ID,
        barber_id=BARBER_ID,
        appointment_date=date(2026, 9, 7),
        timezone="America/Sao_Paulo",
        slots=[
            AvailabilitySlot(
                starts_at=datetime(2026, 9, 7, 9, tzinfo=timezone),
                ends_at=datetime(2026, 9, 7, 9, 30, tzinfo=timezone),
            )
        ],
    )
    model_client = StubTextGenerationClient()
    booking_service = AsyncMock(spec=AssistantBookingService)
    agent = AvailabilityAgent(
        cast(AvailabilityService, availability_service),
        cast(AssistantBookingService, booking_service),
        model_client,
        "gpt-5.6-luna",
    )

    result = asyncio.run(
        agent.reply(
            business_id=BUSINESS_ID,
            barber_id=BARBER_ID,
            appointment_date=date(2026, 9, 7),
            message="Tem horário pela manhã?",
        )
    )

    assert result.reply == "Tenho horário às 09:00."
    assert result.model == "gpt-5.6-luna"
    assert "2026-09-07T09:00:00-03:00" in model_client.user_input
    assert "Tem horário pela manhã?" in model_client.user_input
    assert str(BUSINESS_ID) not in model_client.user_input


def test_agent_requires_confirmation_before_booking() -> None:
    timezone = ZoneInfo("America/Sao_Paulo")
    starts_at = datetime(2026, 9, 7, 10, 30, tzinfo=timezone)
    availability_service = AsyncMock(spec=AvailabilityService)
    availability_service.list_available_slots.return_value = AvailabilityResponse(
        business_id=BUSINESS_ID,
        barber_id=BARBER_ID,
        appointment_date=date(2026, 9, 7),
        timezone="America/Sao_Paulo",
        slots=[AvailabilitySlot(starts_at=starts_at, ends_at=starts_at.replace(hour=11))],
    )
    booking_service = AsyncMock(spec=AssistantBookingService)
    conversation_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    booking_service.propose.return_value = SimpleNamespace(
        id=conversation_id,
        proposed_starts_at=starts_at.astimezone(UTC),
    )
    model_client = StubTextGenerationClient()
    model_client.intent = AssistantIntent(
        intent=AssistantIntentName.SELECT_SLOT,
        selected_time=time(10, 30, tzinfo=UTC),
    )
    agent = AvailabilityAgent(
        cast(AvailabilityService, availability_service),
        cast(AssistantBookingService, booking_service),
        model_client,
        "gpt-5.6-luna",
    )

    result = asyncio.run(
        agent.reply(
            business_id=BUSINESS_ID,
            barber_id=BARBER_ID,
            appointment_date=date(2026, 9, 7),
            customer_id=UUID("fea93fe2-cbae-449b-b0f5-5d793e3ad4b2"),
            message="Quero às 10:30",
        )
    )

    assert result.action == "confirmation_required"
    assert result.conversation_id == conversation_id
    assert result.starts_at == starts_at
    assert "10:30" in result.reply
    booking_service.confirm.assert_not_awaited()
