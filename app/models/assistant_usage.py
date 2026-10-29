"""Shared request counters for the business assistant."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AssistantUsage(Base):
    __tablename__ = "assistant_usage_limits"

    business_id: Mapped[UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), primary_key=True
    )
    minute_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    minute_requests: Mapped[int] = mapped_column(Integer)
    hour_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    hour_requests: Mapped[int] = mapped_column(Integer)
