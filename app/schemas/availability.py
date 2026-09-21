"""API contracts for barber schedules and available time slots."""

from datetime import date, time
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class BarberScheduleUpsert(BaseModel):
    """Working window and slot length for one weekday."""

    starts_at: time
    ends_at: time
    slot_duration_minutes: int = Field(default=30, ge=5, le=480)
    break_starts_at: time | None = None
    break_ends_at: time | None = None

    @model_validator(mode="after")
    def validate_time_range(self) -> "BarberScheduleUpsert":
        """Reject empty or reversed working windows."""
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be later than starts_at")
        if (self.break_starts_at is None) != (self.break_ends_at is None):
            raise ValueError("both break times must be informed")
        if self.break_starts_at is not None and self.break_ends_at is not None:
            if not (self.starts_at <= self.break_starts_at < self.break_ends_at <= self.ends_at):
                raise ValueError("break must be inside the working window")
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
    break_starts_at: time | None
    break_ends_at: time | None


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


class BarberTimeOffCreate(BaseModel):
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    reason: str = Field(default="Bloqueio de agenda", min_length=2, max_length=200)

    @model_validator(mode="after")
    def validate_range(self) -> "BarberTimeOffCreate":
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be later than starts_at")
        return self


class BarberTimeOffResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    barber_id: UUID
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    reason: str
