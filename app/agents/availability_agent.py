"""Customer-service agent grounded in the real barber availability."""

import json
from datetime import date
from typing import Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from app.schemas.assistant import (
    AssistantIntent,
    AssistantIntentName,
    AssistantMessageResponse,
)
from app.services.assistant_booking import AssistantBookingService
from app.services.availability import AvailabilityService

INSTRUCTIONS = """You are the scheduling assistant for a barbershop.
Reply in Brazilian Portuguese, clearly and briefly.
Use only the available slots supplied in the scheduling context.
Never invent a time, claim that a booking was created, or expose internal identifiers.
If there are no slots, explain that the selected day has no availability.
Present times in HH:MM format and offer at most five options at once.
"""

INTENT_INSTRUCTIONS = """Classify a Brazilian Portuguese scheduling message.
Use select_slot when the customer chooses a specific HH:MM time.
Use confirm_booking only for an explicit confirmation such as 'confirmo', 'sim, pode marcar',
or 'pode agendar'. A time selection alone is never a confirmation.
Use check_availability for questions, ambiguity, rejection, cancellation, or any other message.
Set selected_time only for select_slot.
"""


class TextGenerationClient(Protocol):
    """Minimal interface required from a language model provider."""

    async def generate(self, *, instructions: str, user_input: str) -> str:
        """Generate a text reply."""
        ...

    async def interpret(
        self,
        *,
        instructions: str,
        user_input: str,
        response_format: type[BaseModel],
    ) -> BaseModel:
        """Return a structured interpretation."""
        ...


class AvailabilityAgent:
    """Answer customers using availability calculated by the domain service."""

    def __init__(
        self,
        availability: AvailabilityService,
        booking: AssistantBookingService,
        model_client: TextGenerationClient,
        model_name: str,
    ) -> None:
        self._availability = availability
        self._booking = booking
        self._model_client = model_client
        self._model_name = model_name

    async def reply(
        self,
        *,
        business_id: UUID,
        barber_id: UUID,
        appointment_date: date,
        message: str,
        customer_id: UUID | None = None,
        conversation_id: UUID | None = None,
    ) -> AssistantMessageResponse:
        """Interpret one message and execute only validated workflow operations."""
        availability = await self._availability.list_available_slots(
            business_id=business_id,
            barber_id=barber_id,
            appointment_date=appointment_date,
        )
        interpretation = await self._model_client.interpret(
            instructions=INTENT_INSTRUCTIONS,
            user_input=message,
            response_format=AssistantIntent,
        )
        intent = AssistantIntent.model_validate(interpretation)

        if intent.intent == AssistantIntentName.SELECT_SLOT and intent.selected_time is not None:
            if customer_id is None:
                return AssistantMessageResponse(
                    reply=(
                        "Encontrei o horário escolhido. Para continuar, preciso identificar "
                        "seu cadastro de cliente."
                    ),
                    model=self._model_name,
                    action="customer_required",
                )
            proposal = await self._booking.propose(
                business_id=business_id,
                barber_id=barber_id,
                customer_id=customer_id,
                appointment_date=appointment_date,
                selected_time=intent.selected_time,
            )
            if proposal is None:
                return AssistantMessageResponse(
                    reply="Esse horário não está mais disponível. Escolha outro horário livre.",
                    model=self._model_name,
                )
            local_starts_at = proposal.proposed_starts_at.astimezone(
                ZoneInfo(availability.timezone)
            )
            return AssistantMessageResponse(
                reply=(
                    f"Posso agendar para {local_starts_at:%H:%M}. "
                    "Responda 'Confirmo' para concluir."
                ),
                model=self._model_name,
                action="confirmation_required",
                conversation_id=proposal.id,
                starts_at=local_starts_at,
            )

        if intent.intent == AssistantIntentName.CONFIRM_BOOKING:
            if conversation_id is None:
                return AssistantMessageResponse(
                    reply="Não há horário pendente. Escolha um horário antes de confirmar.",
                    model=self._model_name,
                )
            appointment = await self._booking.confirm(
                business_id=business_id,
                barber_id=barber_id,
                conversation_id=conversation_id,
            )
            local_starts_at = appointment.starts_at.astimezone(ZoneInfo(availability.timezone))
            return AssistantMessageResponse(
                reply=f"Agendamento realizado para {local_starts_at:%d/%m às %H:%M}.",
                model=self._model_name,
                action="booked",
                conversation_id=conversation_id,
                appointment_id=appointment.id,
                starts_at=local_starts_at,
            )

        context = json.dumps(
            {
                "appointment_date": availability.appointment_date.isoformat(),
                "timezone": availability.timezone,
                "slots": [slot.model_dump(mode="json") for slot in availability.slots],
            },
            ensure_ascii=False,
        )
        user_input = f"Scheduling context: {context}\n\nCustomer message: {message}"
        answer = await self._model_client.generate(
            instructions=INSTRUCTIONS,
            user_input=user_input,
        )
        return AssistantMessageResponse(reply=answer, model=self._model_name)
