"""Authenticated owner belonging to one business."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class User(Base):
    """An account authorized to manage one barbershop."""

    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('owner', 'barber')", name="ck_users_role"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="owner", nullable=False)
    barber_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("barbers.id", ondelete="CASCADE"), unique=True, nullable=True
    )
    pending_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    email_verification_code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email_verification_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
