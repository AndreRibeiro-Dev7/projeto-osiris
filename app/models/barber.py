"""Barber entity belonging to a business."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.barber_schedule import BarberSchedule
    from app.models.business import Business


class Barber(Base):
    """Professional who offers appointments at one barbershop."""

    __tablename__ = "barbers"
    __table_args__ = (UniqueConstraint("business_id", "phone", name="uq_barbers_business_phone"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    business: Mapped[Business] = relationship(back_populates="barbers")
    appointments: Mapped[list[Appointment]] = relationship(back_populates="barber")
    schedules: Mapped[list[BarberSchedule]] = relationship(
        back_populates="barber", cascade="all, delete-orphan"
    )
