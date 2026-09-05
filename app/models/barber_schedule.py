"""Weekly working hours configured for a barber."""

from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Time, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.barber import Barber


class BarberSchedule(Base):
    """One barber's recurring working window for a weekday."""

    __tablename__ = "barber_schedules"
    __table_args__ = (
        UniqueConstraint("barber_id", "weekday", name="uq_barber_schedules_barber_weekday"),
        CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_barber_schedules_weekday"),
        CheckConstraint("ends_at > starts_at", name="ck_barber_schedules_valid_time_range"),
        CheckConstraint(
            "slot_duration_minutes BETWEEN 5 AND 480",
            name="ck_barber_schedules_slot_duration",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    barber_id: Mapped[UUID] = mapped_column(
        ForeignKey("barbers.id", ondelete="CASCADE"), nullable=False
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_at: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)
    ends_at: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)
    slot_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)

    barber: Mapped[Barber] = relationship(back_populates="schedules")
