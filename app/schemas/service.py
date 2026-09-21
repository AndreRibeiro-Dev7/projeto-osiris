"""API contracts for the service catalog."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ServiceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    duration_minutes: int = Field(ge=5, le=480)
    price_cents: int = Field(ge=0)


class ServiceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    duration_minutes: int | None = Field(default=None, ge=5, le=480)
    price_cents: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class ServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    name: str
    description: str | None
    duration_minutes: int
    price_cents: int
    is_active: bool
    created_at: datetime
