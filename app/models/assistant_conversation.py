"""Pending booking state for a customer conversation."""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AssistantConversation(Base):
    """A slot proposal waiting for explicit customer confirmation."""

    __tablename__ = "assistant_conversations"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    barber_id: Mapped[UUID] = mapped_column(
        ForeignKey("barbers.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    appointment_date: Mapped[date] = mapped_column(Date, nullable=False)
    proposed_starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    proposed_ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    appointment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
