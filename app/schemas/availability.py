"""API contracts for barber schedules and available time slots."""

from datetime import date, time
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class BarberScheduleUpsert(BaseModel):
    """Working window and slot length for one weekday."""

    starts_at: time
    ends_at: time
    slot_duration_minutes: int = Field(default=30, ge=5, le=480)

    @model_validator(mode="after")
    def validate_time_range(self) -> "BarberScheduleUpsert":
        """Reject empty or reversed working windows."""
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be later than starts_at")
        return self


class BarberScheduleResponse(BaseModel):
    """Persisted recurring schedule for one barber and weekday."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    barber_id: UUID
    weekday: int
    starts_at: time
    ends_at: time
    slot_duration_minutes: int


class AvailabilitySlot(BaseModel):
    """One available interval expressed in the business timezone."""

    starts_at: AwareDatetime
    ends_at: AwareDatetime


class AvailabilityResponse(BaseModel):
    """Available slots for one barber on a local business date."""

    business_id: UUID
    barber_id: UUID
    appointment_date: date
    timezone: str
    slots: list[AvailabilitySlot]
