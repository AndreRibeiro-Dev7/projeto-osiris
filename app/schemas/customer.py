"""API contracts for customer registration."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CustomerCreate(BaseModel):
    """Data required to register a customer."""

    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=8, max_length=30)
    notes: str | None = Field(default=None, max_length=1000)
    birth_date: date | None = None


class CustomerUpdate(BaseModel):
    """Editable customer contact data."""

    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=8, max_length=30)
    notes: str | None = Field(default=None, max_length=1000)
    birth_date: date | None = None


class CustomerResponse(BaseModel):
    """Public representation of a customer."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    full_name: str
    phone: str
    notes: str | None
    birth_date: date | None
    created_at: datetime


class CustomerPortfolioEntry(BaseModel):
    """Aggregated customer metrics used by the portfolio export."""

    id: UUID
    full_name: str
    phone: str
    created_at: datetime
    appointments: int
    completed: int
    no_show: int
    total_spent_cents: int
    last_visit_at: datetime | None = None
    loyalty_enabled: bool
    loyalty_progress: int
    loyalty_target: int
    loyalty_rewards: int
    loyalty_rewards_redeemed: int
    loyalty_rewards_available: int
    loyalty_reward: str
