"""Persistent recovery codes and abuse limits, shared by all API workers."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class BookingAccessChallenge(Base):
    __tablename__ = "booking_access_challenges"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    subject_hash: Mapped[str] = mapped_column(String(64), unique=True)
    code_hash: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    requests: Mapped[int] = mapped_column(Integer, default=0)


class BookingAccessThrottle(Base):
    __tablename__ = "booking_access_throttles"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    requests: Mapped[int] = mapped_column(Integer, default=0)
