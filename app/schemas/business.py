"""API contracts for barbershop registration."""

from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator


def validate_timezone(value: str) -> str:
    """Ensure scheduling receives a valid IANA timezone name."""
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as error:
        raise ValueError("Timezone must be a valid IANA name.") from error
    return value


class BusinessCreate(BaseModel):
    """Data required to register a barbershop."""

    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=8, max_length=30)
    timezone: str = Field(default="America/Sao_Paulo", min_length=1, max_length=64)
    loyalty_enabled: bool = True
    loyalty_target: int = Field(default=10, ge=2, le=50)
    loyalty_reward: str = Field(default="1 atendimento grátis", min_length=2, max_length=120)
    monthly_revenue_goal_cents: int = Field(default=0, ge=0, le=1_000_000_000)

    _validate_timezone = field_validator("timezone")(validate_timezone)


class BusinessUpdate(BaseModel):
    """Editable barbershop profile."""

    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=8, max_length=30)
    timezone: str = Field(min_length=1, max_length=64)
    loyalty_enabled: bool = True
    loyalty_target: int = Field(default=10, ge=2, le=50)
    loyalty_reward: str = Field(default="1 atendimento grátis", min_length=2, max_length=120)
    monthly_revenue_goal_cents: int = Field(default=0, ge=0, le=1_000_000_000)

    _validate_timezone = field_validator("timezone")(validate_timezone)


class BusinessResponse(BaseModel):
    """Public representation of a barbershop."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    phone: str
    timezone: str
    loyalty_enabled: bool
    loyalty_target: int
    loyalty_reward: str
    monthly_revenue_goal_cents: int
    created_at: datetime
