"""Business entity representing one barbershop tenant."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.barber import Barber
    from app.models.customer import Customer
    from app.models.expense import Expense
    from app.models.service import Service


class Business(Base):
    """A barbershop served by the platform."""

    __tablename__ = "businesses"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="America/Sao_Paulo", nullable=False)
    loyalty_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    loyalty_target: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    loyalty_reward: Mapped[str] = mapped_column(
        String(120), default="1 atendimento grátis", nullable=False
    )
    monthly_revenue_goal_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    barbers: Mapped[list[Barber]] = relationship(
        back_populates="business", cascade="all, delete-orphan"
    )
    customers: Mapped[list[Customer]] = relationship(
        back_populates="business", cascade="all, delete-orphan"
    )
    appointments: Mapped[list[Appointment]] = relationship(back_populates="business")
    services: Mapped[list[Service]] = relationship(back_populates="business", cascade="all, delete-orphan")
    expenses: Mapped[list[Expense]] = relationship(back_populates="business", cascade="all, delete-orphan")
