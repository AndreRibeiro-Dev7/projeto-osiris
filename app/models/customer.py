"""Customer entity belonging to a business."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.business import Business


class Customer(Base):
    """Person who can schedule a service at one barbershop."""

    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("business_id", "phone", name="uq_customers_business_phone"),
        CheckConstraint(
            "loyalty_rewards_redeemed >= 0",
            name="ck_customers_loyalty_rewards_redeemed_non_negative",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    loyalty_rewards_redeemed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    business: Mapped[Business] = relationship(back_populates="customers")
    appointments: Mapped[list[Appointment]] = relationship(back_populates="customer")
