"""API contracts for barber registration."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BarberCreate(BaseModel):
    """Data required to register a barber."""

    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=8, max_length=30)


class BarberResponse(BaseModel):
    """Public representation of a barber."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    full_name: str
    phone: str
    is_active: bool
    created_at: datetime
