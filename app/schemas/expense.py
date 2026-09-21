"""Expense API contracts."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ExpenseCategory = Literal["rent", "supplies", "utilities", "marketing", "taxes", "other"]


class ExpenseCreate(BaseModel):
    category: ExpenseCategory
    description: str = Field(min_length=2, max_length=500)
    amount_cents: int = Field(gt=0)
    occurred_on: date
    is_fixed: bool = False


class ExpenseUpdate(BaseModel):
    category: ExpenseCategory
    description: str = Field(min_length=2, max_length=500)
    amount_cents: int = Field(gt=0)
    occurred_on: date
    is_fixed: bool = False


class ExpenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    category: str
    description: str
    amount_cents: int
    occurred_on: date
    is_fixed: bool
    is_paid: bool
    paid_at: datetime | None
    created_at: datetime
