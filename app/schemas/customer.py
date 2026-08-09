"""API contracts for customer registration."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CustomerCreate(BaseModel):
    """Data required to register a customer."""

    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=8, max_length=30)


class CustomerResponse(BaseModel):
    """Public representation of a customer."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    full_name: str
    phone: str
    created_at: datetime
