"""Deterministic booking operations requested through the assistant."""

from datetime import date, time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidSchedulingReferenceError, ResourceNotFoundError
from app.models.appointment import Appointment
from app.models.assistant_conversation import AssistantConversation
from app.repositories.assistant_conversation import AssistantConversationRepository
from app.repositories.customer import CustomerRepository
from app.schemas.appointment import AppointmentCreate
from app.services.appointment import AppointmentService
from app.services.availability import AvailabilityService


class AssistantBookingService:
    """Store a proposal and create it only after explicit confirmation."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._availability = AvailabilityService(session)
        self._appointments = AppointmentService(session)
        self._conversations = AssistantConversationRepository(session)
        self._customers = CustomerRepository(session)

    async def propose(
        self,
        *,
        business_id: UUID,
        barber_id: UUID,
        customer_id: UUID,
        appointment_date: date,
        selected_time: time,
    ) -> AssistantConversation | None:
        """Persist a proposal only when the customer and slot are valid."""
        customer = await self._customers.get_by_id(customer_id)
        if customer is None:
            raise ResourceNotFoundError("Customer not found.")
        if customer.business_id != business_id:
            raise InvalidSchedulingReferenceError("Customer does not belong to this business.")

        availability = await self._availability.list_available_slots(
            business_id=business_id,
            barber_id=barber_id,
            appointment_date=appointment_date,
        )
        local_selected_time = selected_time.replace(tzinfo=None)
        slot = next(
            (
                item
                for item in availability.slots
                if item.starts_at.timetz().replace(tzinfo=None) == local_selected_time
            ),
            None,
        )
        if slot is None:
            return None

        conversation = await self._conversations.create(
            business_id=business_id,
            barber_id=barber_id,
            customer_id=customer_id,
            appointment_date=appointment_date,
            starts_at=slot.starts_at,
            ends_at=slot.ends_at,
        )
        await self._session.commit()
        await self._session.refresh(conversation)
        return conversation

    async def confirm(
        self,
        *,
        business_id: UUID,
        barber_id: UUID,
        conversation_id: UUID,
    ) -> Appointment:
        """Revalidate and book the proposal exactly once."""
        conversation = await self._conversations.get_for_update(conversation_id)
        if conversation is None or conversation.business_id != business_id:
            raise ResourceNotFoundError("Assistant conversation not found.")
        if conversation.barber_id != barber_id:
            raise InvalidSchedulingReferenceError("Conversation belongs to another barber.")
        if conversation.appointment_id is not None:
            return await self._appointments.get(conversation.appointment_id)

        appointment = await self._appointments.create(
            business_id,
            AppointmentCreate(
                barber_id=conversation.barber_id,
                customer_id=conversation.customer_id,
                starts_at=conversation.proposed_starts_at,
                ends_at=conversation.proposed_ends_at,
                notes="Agendamento criado pelo assistente.",
            ),
        )
        conversation.appointment_id = appointment.id
        await self._session.commit()
        return appointment
