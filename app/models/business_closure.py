"""Business-wide closed calendar dates."""
from datetime import date
from uuid import UUID, uuid4
from sqlalchemy import Date, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class BusinessClosure(Base):
    __tablename__ = "business_closures"
    __table_args__ = (UniqueConstraint("business_id", "closure_date", name="uq_business_closures_date"),)
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    closure_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
