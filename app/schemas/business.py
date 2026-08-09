"""API contracts for barbershop registration."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BusinessCreate(BaseModel):
    """Data required to register a barbershop."""

    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=8, max_length=30)
    timezone: str = Field(default="America/Sao_Paulo", min_length=1, max_length=64)


class BusinessResponse(BaseModel):
    """Public representation of a barbershop."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    phone: str
    timezone: str
    created_at: datetime
