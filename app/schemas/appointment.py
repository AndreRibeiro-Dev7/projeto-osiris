"""API contracts for scheduling appointments."""

from datetime import datetime
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.models.appointment import AppointmentStatus


class AppointmentCreate(BaseModel):
    """Data required to reserve a time interval with a barber."""

    barber_id: UUID
    customer_id: UUID
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_time_range(self) -> "AppointmentCreate":
        """Reject ranges whose end is not later than their start."""
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be later than starts_at")
        return self


class AppointmentResponse(BaseModel):
    """Public representation of a scheduled appointment."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    barber_id: UUID
    customer_id: UUID
    starts_at: datetime
    ends_at: datetime
    status: AppointmentStatus
    notes: str | None
    created_at: datetime
