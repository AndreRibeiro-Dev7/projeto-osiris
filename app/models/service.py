"""Service catalog offered by a business."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.business import Business


class Service(Base):
    """One bookable service from a barbershop catalog."""

    __tablename__ = "services"
    __table_args__ = (
        UniqueConstraint("business_id", "name", name="uq_services_business_name"),
        CheckConstraint("duration_minutes BETWEEN 5 AND 480", name="ck_services_duration"),
        CheckConstraint("price_cents >= 0", name="ck_services_price"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    business: Mapped[Business] = relationship(back_populates="services")
    appointments: Mapped[list[Appointment]] = relationship(back_populates="service")
