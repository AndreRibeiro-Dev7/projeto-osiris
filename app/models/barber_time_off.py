"""Exceptional periods when a barber is unavailable."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.barber import Barber


class BarberTimeOff(Base):
    """A one-off absence that removes matching appointment slots."""

    __tablename__ = "barber_time_off"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_barber_time_off_valid_range"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    barber_id: Mapped[UUID] = mapped_column(
        ForeignKey("barbers.id", ondelete="CASCADE"), nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False, default="Bloqueio de agenda")

    barber: Mapped[Barber] = relationship(back_populates="time_off_periods")
