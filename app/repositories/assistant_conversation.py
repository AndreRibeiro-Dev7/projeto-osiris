"""Persistence for pending assistant booking proposals."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant_conversation import AssistantConversation


class AssistantConversationRepository:
    """Create and lock pending booking conversations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        business_id: UUID,
        barber_id: UUID,
        customer_id: UUID,
        appointment_date: date,
        starts_at: datetime,
        ends_at: datetime,
    ) -> AssistantConversation:
        conversation = AssistantConversation(
            business_id=business_id,
            barber_id=barber_id,
            customer_id=customer_id,
            appointment_date=appointment_date,
            proposed_starts_at=starts_at,
            proposed_ends_at=ends_at,
        )
        self._session.add(conversation)
        await self._session.flush()
        return conversation

    async def get_for_update(self, conversation_id: UUID) -> AssistantConversation | None:
        statement = (
            select(AssistantConversation)
            .where(AssistantConversation.id == conversation_id)
            .with_for_update()
        )
        return (await self._session.scalars(statement)).one_or_none()
