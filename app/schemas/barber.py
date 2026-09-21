"""API contracts for barber registration."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BarberCreate(BaseModel):
    """Data required to register a barber."""

    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=8, max_length=30)
    commission_percentage: int = Field(default=0, ge=0, le=100)


class BarberUpdate(BaseModel):
    """Editable professional settings."""

    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, min_length=8, max_length=30)
    commission_percentage: int | None = Field(default=None, ge=0, le=100)
    is_active: bool | None = None


class BarberResponse(BaseModel):
    """Public representation of a barber."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    full_name: str
    phone: str
    is_active: bool
    commission_percentage: int
    created_at: datetime
